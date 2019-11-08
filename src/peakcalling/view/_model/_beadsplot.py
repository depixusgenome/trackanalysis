#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"beads plot status"
from dataclasses   import dataclass, field
from typing        import Dict, Any, Set, Tuple, Union, Optional, Iterable, List

import numpy as np

from cleaning.names import NAMES as _ExceptionNames
from model.plots          import PlotAttrs, defaultfigsize, PlotTheme
from taskmodel            import RootTask
from taskmodel.processors import TaskCacheList
from tasksequences        import StretchFactor
from view.threaded        import DisplayModel
from ._control            import TasksModelController
from ._columns            import getcolumn, INVISIBLE

NAME: str = 'peakcalling.view.beads'


class BeadsPlotTheme(PlotTheme):
    "plot theme"
    def __init__(self, name):
        super().__init__(name = name)
        self.boundsdelta = .3

    def newbounds(self, curr, arr, force):
        "Sets the range boundaries"
        if len(arr) == 0:
            return dict(start        = 0., end          = 1.,
                        max_interval = 1., min_interval = 1.,
                        reset_start  = 0., reset_end    = 1.)

        vmin = np.nanmin(arr)
        if np.isnan(vmin):
            vmin = 0.

        vmax = np.nanmax(arr)
        if np.isnan(vmax):
            vmax = vmin + 1.

        rng = max(1e-5, (vmax-vmin))
        rng = rng*self.overshoot*.5
        if vmax != 0.:
            vmin -= rng
        if vmax != 100.:
            vmax += rng

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
class BeadsScatterPlotStatus:
    """beads plot status"""
    name:         str                      = NAME
    hairpins:     Set[str]                 = field(default_factory = set)
    orientations: Set[str]                 = field(default_factory = set)
    beads:        Dict[RootTask, Set[int]] = field(default_factory = dict)
    roots:        Set[RootTask]            = field(default_factory = set)

    def masked(
            self,
            root:    Union[None, TaskCacheList, RootTask] = None,
            bead:    Optional[int]                        = None,
            hairpin: Optional[str]                        = None
    ) -> bool:
        "return whether the item is masked"
        if isinstance(root, TaskCacheList):
            root = root.model[0] if root.model else None
        return (
            (bead is None and root in self.roots)  # don't test unless specifically required
            or hairpin in self.hairpins
            or bead    in self.beads.get(root, ())
        )

@dataclass  # pylint: disable=too-many-instance-attributes
class BeadsScatterPlotConfig(BasePlotConfig):
    "Information about the current fovs displayed"
    name:    str            = NAME
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
