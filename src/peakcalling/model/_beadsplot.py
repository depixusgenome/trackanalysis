#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"beads plot status"
from dataclasses   import dataclass, field
from typing        import Dict, Any, Set, Tuple, Union, Optional, Iterable, List

import numpy as np
import pandas as pd

from cleaning.names import NAMES as _ExceptionNames
from model.plots          import PlotAttrs, defaultfigsize, PlotTheme
from taskmodel            import RootTask
from taskmodel.processors import TaskCacheList
from tasksequences        import StretchFactor
from view.threaded        import DisplayModel
from ._control            import TasksModelController
from ._columns            import getcolumn, INVISIBLE

DFFilter  = Dict[Tuple[str, ...], Union[list, 'Slice']]
NAME: str = 'peakcalling.view.beads'
_DFLT     = dict(
    start        = 0., end          = 1.,
    max_interval = 1., min_interval = 1.,
    reset_start  = 0., reset_end    = 1.
)


class BeadsPlotTheme(PlotTheme):
    "plot theme"
    def __init__(self, name):
        super().__init__(name = name)
        self.boundsdelta       = .3

    def newbounds(self, curr, arr, force):
        "Sets the range boundaries"
        if len(arr) == 0:
            return _DFLT
        try:
            out = np.isnan(np.asarray(arr, dtype = np.float_))
        except TypeError:
            out = np.isnan([float(i) for i in arr])

        if np.all(out):
            return _DFLT

        vmin = np.nanmin(arr)
        vmax = np.nanmax(arr)

        rng = max(5e-5, (vmax-vmin))
        rng = rng*self.overshoot*.5
        vmin -= rng if vmin != 0.   else 5e-5
        vmax += rng if vmax != 100. else 5e-5

        rng = max(5e-5, (vmax-vmin))
        info = dict(
            max_interval = rng*(1.+self.boundsovershoot),
            min_interval = rng*self.overshoot,
            start        = vmin if curr.start >= vmax else max(curr.start, vmin),
            end          = vmax if curr.end <= vmin else max(curr.end, vmax),
            reset_start  = vmin,
            reset_end    = vmax
        )

        if (
                force
                or (curr.end - curr.start) < rng * self.boundsdelta
                or (curr.end - curr.start) * self.boundsdelta > rng
        ):
            info.update(start = vmin, end = vmax)
        return info

@dataclass  # pylint: disable=too-many-instance-attributes
class BasePlotConfig:
    "Information about the current fovs displayed"
    stretch:        float = StretchFactor.DNA.value
    closest:        int   = 10
    tracknames:     str   = 'simple'  # or full or order
    refname:        str   = 'ref'
    trackordername: str   = 'track'
    statustag: Dict[str, str] = field(
        default_factory = lambda: {
            "< baseline":     f"{INVISIBLE*0}< baseline",
            "baseline":       f"{INVISIBLE*1}baseline",
            "truepos":        f"{INVISIBLE*2}identified",
            "falseneg":       f"{INVISIBLE*3}missing",
            "falsepos":       f"{INVISIBLE*4}unidentified",
            "":               f"{INVISIBLE*5}blockage",
            "singlestrand":   f"{INVISIBLE*6}single strand",
            "> singlestrand": f"{INVISIBLE*7}> single strand",
        }
    )
    beadstatustag: Dict[str, str] = field(
        default_factory = lambda: {
            "ok":       "ok",
            "empty":    INVISIBLE   + "no blockages",
            "bug":      INVISIBLE*2 + "bug",
            "unknown":  INVISIBLE*2 + "?",
            **{i: INVISIBLE + j for i, j in _ExceptionNames.items()}
        }
    )

    def tracknameconversion(self, names: Iterable[str]) -> Dict[str, str]:
        "change track names to something simpler"
        if self.tracknames == 'full':
            return {}

        info = {i: i[i.find('-')+1:] for i in names}
        if len(info) == 0:
            return {}

        if len(info) == 1:
            return {next(iter(info)): ''}

        if self.tracknames == 'order' or len(set(info.values())) == 1:
            return {i: self.trackordername+' '+i[:i.find('-')] for i in info}

        keys   = {i: j.split('_') for i, j in info.items()}
        itr    = iter(keys.values())
        common = set(next(itr))
        for i in itr:
            common.intersection_update(i)

        if not common:
            return {}

        out = {i: '_'.join(k for k in j if k not in common) for i, j in keys.items()}
        if '' in out.values():
            out[next(i for i, j in out.items() if j == '')] = self.refname
        return {i: i[:i.find('-')+1]+j for i, j  in out.items()}

@dataclass
class Slice:
    "like slice but read/write"
    start: Union[float, int, None] = None
    stop:  Union[float, int, None] = None


class NotSet(set):
    "the opposite of a set"

@dataclass
class BeadsScatterPlotStatus:
    """beads plot status"""
    name:         str                      = NAME
    hairpins:     Set[str]                 = field(default_factory = set)
    orientations: Set[str]                 = field(default_factory = set)
    beads:        Dict[RootTask, Set[int]] = field(default_factory = dict)
    roots:        Set[RootTask]            = field(default_factory = set)
    ranges:       DFFilter                 = field(default_factory = dict)

    def filter(self, dframe) -> pd.DataFrame:
        "filter the dataframe"
        if dframe.shape[0] == 0:
            return dframe

        found = False
        for col, rng in self.ranges.items():
            if rng == Slice():
                continue

            dframe, cur, found = self.__filter_get(dframe, col, found)
            if cur is None:
                continue

            for i in cur.values if isinstance(cur, pd.Series) else (cur,):
                try:
                    if isinstance(cur.index, pd.MultiIndex):
                        i['_dummy_'] = np.arange(i.shape[0])
                        i.set_index('_dummy_', append = True, inplace = True)

                    i.drop(index = self.__filter_inds(i, col[-1], rng), inplace = True)
                finally:
                    if isinstance(i.index, pd.MultiIndex):
                        i.reset_index('_dummy_', drop = True, inplace = True)

        return dframe

    def masked(
            self,
            root:    Union[None, TaskCacheList, RootTask] = None,
            bead:    Optional[int]                        = None,
            hairpin: Optional[str]                        = None
    ) -> bool:
        "return whether the item is masked"
        if isinstance(root, TaskCacheList):
            root = root.model[0] if root.model else None

        if bead is None and root in self.roots:  # don't test unless specifically required
            return True

        if hairpin in self.hairpins:
            return True

        lst = self.beads.get(root, ())
        return bead not in lst if isinstance(lst, NotSet) else bead in lst

    @staticmethod
    def __filter_get(
            dframe: pd.DataFrame, col: Tuple[str,...], found: bool
    ) -> Tuple[pd.DataFrame, Optional[pd.DataFrame], bool]:

        cur = dframe
        for i in col[:-1]:
            if i not in cur:
                return dframe, None, found
            cur = cur[i]

        if (
                (len(col) == 1 and col[-1] not in cur)
                or (len(col) == 2 and col[-1] not in cur.values[0])
        ):
            return dframe, None, found

        dframe = dframe.copy(True)
        cur    = dframe
        for i in col[:-1]:
            cur[i].values[:] = [i.copy(True) for i in cur[i].values]
            cur              = cur[i]

        return dframe, cur, found

    @staticmethod
    def __filter_inds(cur: pd.DataFrame, col: str, rng: Union[list, Slice]) -> np.ndarray:
        if isinstance(rng, (list, np.ndarray)):
            inds = ~np.isin(cur[col], rng)

        elif rng.start is not None:
            inds = cur[col] < rng.start
            if rng.stop is not None:
                inds |= cur[col] > rng.stop
        else:
            assert rng.stop is not None
            inds = cur[col] > rng.stop
        return cur.index[inds]

@dataclass  # pylint: disable=too-many-instance-attributes
class BeadsScatterPlotConfig(BasePlotConfig):
    "Information about the current fovs displayed"
    name:    str            = NAME
    sorting: Set[str]       = field(default_factory = lambda: {'hairpin', 'track', 'bead'})
    figargs: Dict[str, Any] = field(default_factory = lambda: dict(
        toolbar_sticky   = False,
        toolbar_location = 'above',
        tools            = ['pan,wheel_zoom,box_zoom,save,reset,hover'],
        plot_width       = 1000,
        plot_height      = 600,
        sizing_mode      = defaultfigsize()[-1],
        x_axis_label     = 'bead'
    ))
    yaxis:   Tuple[str, str] = (
        "postions (base pairs = {:.2f} nm⁻¹)", "positions (base pairs)"
    )

    datacolumns: List[str] = field(default_factory = lambda: [
        'hybridisationrate', 'averageduration', 'blockageresolution',
        'baseposition', 'peakposition',
        'status', 'distance', 'closest', 'orientation', 'hairpin'
    ])

    tooltipcolumns: List[Tuple[str,str]] = field(default_factory = lambda: [
        (getcolumn(i).label if i != 'baseposition' else 'z (bp)', f'@{i}')
        for i in (
            'hybridisationrate', 'averageduration', 'blockageresolution',
            'status', 'distance', 'closest', 'orientation',
        )
    ])

    events:    PlotAttrs    = field(
        default_factory = lambda: PlotAttrs(
            '', 'oval',
            fill_color  = '~gray',
            fill_alpha  = .5,
            line_alpha  = 1.,
            line_width  = 2.,
            line_color  = 'color',
            x           = 'x',
            y           = 'baseposition',
            width       = 'hybridisationrate',
            height      = 'blockageresolution',
        )
    )
    blockages: PlotAttrs = field(default_factory = lambda: PlotAttrs(
        'color', 'o', 10, x = 'x', y = 'baseposition', fill_alpha = 0., line_alpha = 0.,
    ))
    bindings:  PlotAttrs = field(default_factory = lambda: PlotAttrs(
        'color', 'x', 10, x = 'x', y = 'bindingposition', alpha = .8
    ))
    colors:    Dict[str, str] = field(default_factory = lambda: {
        "truepos":        "lightgreen",
        "falsepos":       "red",
        "falseneg":       "red",
        "baseline":       "dpxblue",
        "< baseline":     "dpxblue",
        "singlestrand":   "dpxblue",
        "> singlestrand": "dpxblue",
        "":               "lightgreen"
    })
    order:    Dict[str, int] = field(default_factory = lambda: {
        j: i
        for i, j in enumerate((
            "baseline", "< baseline", "singlestrand", "> singlestrand",
            "", "truepos", "falsepos", "falseneg"
        ))
    })

class BeadsScatterPlotModel(DisplayModel[BeadsScatterPlotStatus, BeadsScatterPlotConfig]):
    "model for display the FoVs"
    tasks: TasksModelController

    def __init__(self, **_):
        super().__init__()
        self.tasks = TasksModelController()

    def swapmodels(self, ctrl):
        "swap with models in the controller"
        super().swapmodels(ctrl)
        self.tasks.swapmodels(ctrl)
