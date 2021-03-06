#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"View module showing one or more FoVs"
from   abc       import abstractmethod
from   copy      import copy
from   functools import partial
from   typing    import Dict, List, Iterator, Tuple, Union, Set, Optional, cast

import pandas as pd
import numpy  as np

from   bokeh           import layouts
from   bokeh.models    import ColumnDataSource, FactorRange, HoverTool, Range1d
from   bokeh.plotting  import figure, Figure

from   view.colors     import tohex
from   view.threaded   import ThreadedDisplay
from   taskmodel       import RootTask
from   utils.logconfig import getLogger
from   ..model         import (
    BeadsScatterPlotModel, Processors, COLS, BeadsPlotTheme, Slice
)
from   ._threader import BasePlotter, PlotThreader
from   ._widgets  import JobsStatusBar, JobsHairpinSelect, BeadsPlotSelector

LOGS = getLogger(__name__)


class BeadsScatterPlotWarning(RuntimeWarning):
    "used to warn the user"

@PlotThreader.setup
class BeadsScatterPlot(ThreadedDisplay[BeadsScatterPlotModel]):
    "display the current bead"
    _fig:         Figure
    _expdata:     ColumnDataSource
    _defaultdata: Dict[str, list]
    _theodata:    ColumnDataSource

    def __init__(self, widgets = True, **_):
        super().__init__(**_)
        self._widgets     = (JobsStatusBar(), JobsHairpinSelect()) if widgets else ()
        self._widgets    += (BeadsPlotSelector(),)
        self._plottheme   = BeadsPlotTheme("peakcalling.view.beads.plot.theme")
        self._defaultdata = self.__defaultdata()

    _reset = None   # added in _Threader.setup

    def gettheme(self):
        "get the model theme"
        return self._model.theme

    def getdisplay(self):
        "get the model display"
        return self._model.display

    def getfigure(self) -> Figure:
        "get the model display"
        return self._fig

    @property
    def nfactors(self) -> int:
        "return the number of beads"
        plot = getattr(getattr(self, '_threader'), 'plot', None)
        return plot.nfactors if plot else 1

    def swapmodels(self, ctrl):
        "swap with models in the controller"
        super().swapmodels(ctrl)
        self._plottheme = ctrl.theme.swapmodels(self._plottheme)
        for i in self._widgets:
            if hasattr(i, 'swapmodels'):
                i.swapmodels(ctrl)

    def observe(self, ctrl):
        """observe the controller"""
        for i in self._widgets:
            if hasattr(i, 'observe'):
                i.observe(ctrl, self._model.tasks)

    def createplot(self) -> BasePlotter:
        "runs the display"
        procs = self._model.tasks.processors
        return (
            _HairpinPlot if BasePlotter.ishairpin(procs) else _PeaksPlot
        )(self, procs)

    def hitpoint(self, xval: float) -> Optional[Tuple[RootTask, int]]:
        "get the track & bead"
        return  getattr(
            getattr(getattr(self, '_threader'), 'plot', None),
            'hitpoint',
            lambda _: None
        )(xval)

    def hitposition(self, root, bead) -> Optional[float]:
        "get the track & bead position"
        return  getattr(
            getattr(getattr(self, '_threader'), 'plot', None),
            'hitposition',
            lambda *_: None
        )(root, bead)

    def _addtodoc(self, ctrl, doc):
        "sets the plot up"
        self._addtodoc_data()
        self._addtodoc_fig()
        self._widgets[-1].addtodoc((self,), ctrl, doc)
        if len(self._widgets) == 1:
            return [self._fig]

        itms      = [i.addtodoc(ctrl, doc)[0] for i in self._widgets[:-1]]
        mode      = {'sizing_mode': ctrl.theme.get('main', 'sizingmode', 'fixed')}
        brds      = ctrl.theme.get("main", "borders", 5)
        width     = sum(i.width  for i in itms) + brds
        height    = max(i.height for i in itms) + brds

        return layouts.column(
            [
                layouts.row(
                    [
                        layouts.widgetbox(i, width = i.width, height = i.height)
                        for i in itms
                    ],
                    width  = width, height = height, **mode
                ),
                self._fig
            ],
            width  = max(width, self._fig.plot_width + brds),
            height = height + self._fig.plot_height,
            **mode,
        )

    def _addtodoc_data(self):
        self._defaultdata = self.__defaultdata()
        self._expdata     = ColumnDataSource(self._defaultdata)
        self._theodata    = ColumnDataSource(dict(
            {i: [''] for i in  ('hairpin', 'status', 'color')},
            bindingposition = [0],
            x               = [('track1', '0')]
        ))

    def _addtodoc_fig(self):
        "build a figure"
        fig = figure(
            **self._model.theme.figargs,
            x_range = FactorRange(factors = self._expdata.data['x']),
            y_range = Range1d()
        )

        hover            = fig.select(HoverTool)[0]
        hover.tooltips   = self._model.theme.tooltipcolumns
        hover.toggleable = False
        hover.renderers  = [
            self.attrs(self._model.theme.blockages).addto(fig, source = self._expdata)
        ]
        self.attrs(self._model.theme.events).addto(fig, source = self._expdata)
        self.attrs(self._model.theme.bindings).addto(fig, source = self._theodata)
        self._fig = fig

    def __defaultdata(self):
        strycols = ('hairpin', 'status', 'orientation')
        return dict(
            {i: [''] for i in  strycols},
            color = ['green'],
            **{i: [0.] for i in set(self._model.theme.datacolumns) - set(strycols)},
            x = [('track1', '0')]
        )

class _Plot(BasePlotter[BeadsScatterPlot]):
    parent: BeadsScatterPlot

    def __init__(self, mdl: BeadsScatterPlot, procs: Processors):
        super().__init__(mdl, procs)
        self._data:    pd.DataFrame         = pd.DataFrame({})
        self._factors: List[Tuple[str,...]] = []
        self._xv:      Tuple[np.ndarray, np.ndarray] = (np.empty(0), np.empty(0))

    _expdata:     ColumnDataSource      = BasePlotter.attr()
    _defaultdata: Dict[str, list]       = BasePlotter.attr()
    _theodata:    ColumnDataSource      = BasePlotter.attr()
    _model:       BeadsScatterPlotModel = BasePlotter.attr()
    _plottheme:   BeadsPlotTheme        = BasePlotter.attr()
    _fig:         Figure                = BasePlotter.attr()

    def getfigure(self) -> Figure:
        "get the model display"
        return self._fig

    @property
    def nfactors(self) -> int:
        "return the number of beads"
        return max(1, len(self._factors))

    def hitpoint(self, xval: float) -> Optional[Tuple[RootTask, int]]:
        "get the track & bead"
        if self._isdefault():
            return None

        curf  = self._factors
        lastv = 0.
        last  = self._factors[0]
        for xlabel in copy(self._factors):
            nextv = lastv + 1.
            if xlabel[0] != last[0]:
                nextv += self._fig.x_range.group_padding
            elif len(xlabel) > 2 and xlabel[1] != last[1]:
                nextv += self._fig.x_range.subgroup_padding

            last = xlabel
            if lastv <= xval < nextv:
                break
            lastv = nextv

        ind  = int(last[-2][:last[-2].find('-')])
        try:
            out  = list(self._procs)[ind], int(last[-1])
        except IndexError:
            return None
        return out if curf is self._factors and out[0] is not None else None

    def hitposition(self, root, bead) -> Optional[float]:
        "get the track & bead position"
        if self._isdefault():
            return None

        lastv = 0.
        last  = self._factors[0]
        for xlabel in copy(self._factors):
            nextv = lastv + 1.
            if xlabel[0] != last[0]:
                nextv += self._fig.x_range.group_padding
            elif len(xlabel) > 2 and xlabel[1] != last[1]:
                nextv += self._fig.x_range.subgroup_padding

            ind  = int(xlabel[-2][:xlabel[-2].find('-')])
            try:
                out = list(self._procs)[ind], int(xlabel[-1])
            except IndexError:
                pass
            else:
                if out[0] is root and out[1] == bead:
                    return nextv - .5

            last, lastv = xlabel, nextv

        ind  = int(last[-2][:last[-2].find('-')])
        try:
            out = list(self._procs)[ind], int(last[-1])
        except IndexError:
            pass
        else:
            if out[0] is root and out[1] == bead:
                return nextv - .5
        return None

    def _reset(self):
        "resets the data"
        data, status = self.__compute_expdata()
        if status:
            LOGS.debug("Resetting to defaults")
            exp     = self._defaultdata
            factors = list(exp['x'])
            theo    = {i: j[:0] for i, j in self._theodata.data.items()}
            yield BeadsScatterPlotWarning("No beads available for this plot!"), ""
        else:
            LOGS.debug("Resetting")
            factors = self._xfactors(data)
            theo    = self._from_df(self._compute_theodata(data))
            exp     = self._from_df(self.__set_tags(data))

        self.__simplify_factors(exp, theo, factors, True)
        yield (self._fig.y_range, self.__yrange(data, theo, True))
        yield (self._expdata,      dict(data       = exp))
        yield (self._theodata,     dict(data       = theo))
        yield (self._fig.x_range,  dict(factors    = factors))
        yield (self._fig.yaxis[0], dict(axis_label = self._yaxis()))

    def _isdefault(self) -> bool:
        "whether the plot should be started anew or updated"
        return not self._factors

    def _update(self):
        "streams the data"
        data, status = self.__compute_expdata()

        if status:
            return

        LOGS.debug("Updating")
        factors = self._xfactors(data)
        theo    = self._from_df(self._compute_theodata(data))
        exp     = self._from_df(self.__set_tags(data))
        cnv     = self.__simplify_factors(exp, theo, factors, False)
        yield (self._fig.y_range, self.__yrange(data, theo, False))

        def _call(name: str, old: np.ndarray, new: Dict[str, np.ndarray]):
            src = getattr(self, name)
            if len(next(iter(new.values()), ())):
                src.stream(new)
            if len(old):
                src.patch({'x': ((slice(len(old)), old),)})

        yield ('_expdata',  partial(_call, '_expdata',  cnv[0], exp))
        yield ('_theodata', partial(_call, '_theodata', cnv[1], theo))

        yield (self._fig.x_range, dict(factors = factors))

    def __yrange(self, data, theo, force: bool) -> Dict[str, float]:
        vals = np.concatenate([
            data['baseposition'], theo['bindingposition'],
            [self._fig.y_range.start, self._fig.y_range.end] if not force else []
        ])
        return self._plottheme.newbounds(self._fig.y_range, vals, force)

    def __iter_cache(self) -> Iterator[pd.DataFrame]:
        itr = self.computations('_data', self._model)
        for _, info in itr:
            info = itr.send(info.reset_index())
            info['x'] = [(info.track.values[0], str(info.bead.values[0]))]*len(info)
            yield info

    def __simplify_factors(
            self, exp, theo, factors, reset: bool
    ) -> Tuple[list, ...]:
        xvals    = ([], []) if reset else self._xv
        self._xv = cast(
            Tuple[np.ndarray, np.ndarray],
            tuple(
                np.copy(j) if len(i) == 0 else
                i          if len(j) == 0 else
                np.concatenate([i, j])
                for i, j in zip(xvals, (exp['x'], theo['x']))
            )
        )

        cols   = (exp['x'], theo['x'], factors)
        cnv    = self._model.theme.tracknameconversion(i[-2] for i in self._factors)

        if not cnv and len(factors) > 1 and len(factors[0]) == 2:
            # pylint: disable=unnecessary-comprehension
            for col in cols:
                col[:] = [(i, '', j) for i, j in col]
            return tuple([(i, '', j) for i, j in col] for col in xvals)

        if not cnv:
            return (np.empty(0), np.empty(0))

        for col in cols:
            col[:] = (
                [(cnv.get(str(i), i), '', j) for i, j    in col]
                if len(col) and len(col[0]) == 2 else
                [(i, cnv.get(str(j), j), k)  for i, j, k in col]
            )

        return tuple(
            (
                [(cnv.get(str(i), i), '', j) for i, j    in col]
                if len(col) and len(col[0]) == 2 else
                [(i, cnv.get(str(j), j), k)  for i, j, k in col]
            )
            for col in xvals
        )

    def __set_tags(self, frame):
        def _tag(name):
            return lambda x, y = getattr(self._model.theme, name+'tag'): y.get(x, x)

        return frame.assign(
            **{
                i: frame[i].apply(_tag(i))
                for i in frame.columns
                if hasattr(self._model.theme, i+'tag')
            }
        )

    def __compute_expdata(self) -> Tuple[pd.DataFrame, bool]:
        lst  = [i for i in self._compute_expdata(self.__iter_cache()) if i.shape[0]]
        if not lst:
            return pd.DataFrame(self._defaultdata), True

        colors = tohex(self._model.theme.colors)
        order  = self._model.theme.order
        frame  = (
            pd.concat(lst, sort = False, ignore_index = True)
            .assign(
                color = lambda itm: itm.status.apply(colors.get),
                order = lambda itm: itm.status.apply(order.get)
            )
        )

        frame.sort_values([*self._beadorder(), "order"], ascending = True, inplace = True)
        frame.drop(columns = ['order'], inplace = True)

        frame  = frame.assign(
            **{i: np.NaN for i in set(self._defaultdata) - set(frame.columns)}
        )

        return frame, False

    def _xfactors(self, frame: pd.DataFrame) -> Union[List[str], List[Tuple[str,...]]]:
        frame = (
            frame[['track', 'trackid', 'bead', 'x', *self._factorcols()]]
            .groupby(['trackid', 'bead'])
            .first()
            .reset_index()
        )
        assert ('track1', '0') not in self._factors
        if self._data.shape[0]:
            assert ('track1', '0') not in self._data.x.tolist()
        assert ('track1', '0') not in frame.x.tolist()
        self._data    = (
            pd.concat([self._data,  frame], sort = False, ignore_index = True)
            if self._factors else frame
        )
        self._factors = list(self._sortfactors(self._data).x)
        return list(self._factors)

    @abstractmethod
    def _yaxis(self) -> str:
        pass

    @staticmethod
    @abstractmethod
    def _factorcols() -> List[str]:
        pass

    @abstractmethod
    def _sortfactors(self, data: pd.DataFrame) -> pd.DataFrame:
        pass

    @staticmethod
    @abstractmethod
    def _beadorder() -> List[str]:
        pass

    @abstractmethod
    def _compute_expdata(self, itr: Iterator[pd.DataFrame]) -> Iterator[pd.DataFrame]:
        pass

    @abstractmethod
    def _compute_theodata(self, expdata: pd.DataFrame) -> pd.DataFrame:
        pass

class _HairpinPlot(_Plot):
    @staticmethod
    def _factorcols() -> List[str]:
        return ['hairpin', 'cost']

    def _yaxis(self) -> str:
        return self._model.theme.yaxis[1]

    def _sortfactors(self, data: pd.DataFrame) -> pd.DataFrame:
        sorts = self._model.theme.sorting
        cols  = ['hairpin', 'track', 'bead']
        for i, col in enumerate(cols):
            if col in sorts:
                data.set_index(cols[:i+1], inplace = True)
                out = data.groupby(level = cols[:i+1]).cost.median()
                # don't use pd.DataFrame.assign as it produces errors: pandas is buggy
                data[f"{col[0]}cost"] = out

                data.reset_index(inplace = True)
            else:
                # create a integer type column as pandas will not always succeed at
                # sorting multi-indexes of mixed type.
                itms = data[col].unique()
                itms.sort()
                data[f"{col[0]}cost"] = data[col].apply(itms.tolist().index)

        return data.sort_values(['hcost', 'tcost', 'bcost'])

    @staticmethod
    def _beadorder() -> List[str]:
        return ['hairpin', 'trackid', 'cost']

    def _compute_expdata(self, itr: Iterator[pd.DataFrame]) -> Iterator[pd.DataFrame]:
        def _x(info):
            return lambda x, y = info.iloc[0].x: (x, *y)

        hpin = self._model.display.hairpins
        ori  = self._model.display.orientations
        cols = list(set(self._model.theme.datacolumns) - {'bead', 'cost', 'hairpin'})
        for info in itr:
            info = self.selectbest(hpin, set(), info)
            if info.shape[0] == 0:
                continue

            out  = (
                info.peaks.values[0][cols]
                .assign(
                    hairpin = info.iloc[0]['hpin'],
                    **{i: info.iloc[0][i] for i in ('track', 'trackid', 'bead', 'cost')},
                )
            )
            out['blockageresolution'] *= info.stretch.values[0]
            for i in ori:
                out = out[out['orientation'] != i]
                if out.shape[0] == 0:
                    continue

            self.resetstatus(self._model.theme.closest, out)
            out['x'] = out.hairpin.apply(_x(info))
            yield out

    def _compute_theodata(self, expdata: pd.DataFrame) -> pd.DataFrame:
        if (
                expdata.shape[0] == 0
                or all(expdata[i].tolist() == self._defaultdata[i] for i in ('x', 'baseposition'))
        ):
            return pd.DataFrame({i: j[:0] for i, j in self._theodata.data.items()})

        hpin: Dict[Tuple[str, int], np.ndarray] = {}
        ids:  Set[int]                          = set(expdata.trackid.unique())
        for proc in self._procs.values():
            iproc = id(proc.model[0])
            if iproc in ids:
                for task in proc.model:
                    hpin.update(
                        {(i, iproc): j.peaks for i, j in getattr(task, 'fit', {}).items()}
                    )

        colors   = tohex(self._model.theme.colors)
        cols     = ['hairpin', 'trackid', 'bead', 'closest']
        ind      = expdata.groupby(cols[:-1]).cost.first().index
        bindings = pd.Series([hpin[i[:2]] for i in ind], index = ind, name = 'var')
        data     = (
            bindings.apply(pd.Series)
            .merge(
                bindings.to_frame().drop(columns = ['var']),
                right_index = True,
                left_index  = True
            )
            .reset_index()
            .melt(id_vars= cols[:-1], value_name = cols[-1])
            .drop(columns = ['variable'])
            .dropna()
            .assign(status = 'falseneg', color  = colors['falseneg'])
        )

        data.set_index(cols, inplace = True)
        ind = expdata[expdata.status == 'truepos'].groupby(cols).x.first().index
        data.loc[ind, 'status'] = 'truepos'
        data.loc[ind, 'color']  = colors['truepos']

        data.reset_index(level = 3, inplace = True)
        data = data.join(
            expdata.groupby(cols[:-1]).agg({'hairpin': 'first', 'x': 'first'})
        )

        data.rename(columns = {'closest': 'bindingposition'}, inplace = True)

        cnf = copy(self._model.display)
        cnf.ranges = dict(cnf.ranges)
        for i in ('baseposition', 'closest'):
            if cnf.ranges.get(('peaks', i), Slice()) != Slice():
                cnf.ranges[('bindingposition',)] = cnf.ranges.pop(('peaks', i))
        return cnf.filter(data)

class _PeaksPlot(_Plot):
    @staticmethod
    def _factorcols() -> List[str]:
        return []

    def _yaxis(self) -> str:
        return self._model.theme.yaxis[0].format(1e3/self._model.theme.stretch)

    def _sortfactors(self, data: pd.DataFrame) -> Tuple[List[str], List[str]]:
        data[f"torder"] = data.track.apply(sorted(data.track.unique()).index)
        return data.sort_values(['torder', 'bead'])

    @staticmethod
    def _beadorder() -> List[str]:
        return ['trackid', 'bead']

    def _compute_expdata(self, itr: Iterator[pd.DataFrame]) -> Iterator[pd.DataFrame]:
        stretch = self._model.theme.stretch
        cols    = list({
            'track', 'trackid', 'bead', 'x',
            *(
                i for i in self._model.theme.datacolumns
                if (
                    i != 'baseposition'
                    and not next((j.fit for j in COLS if j.key == i), False)
                )
            )
        })
        return (
            info[cols]
            .assign(
                baseposition       = lambda x: x.peakposition       * stretch,
                blockageresolution = lambda x: x.blockageresolution * stretch
            )
            for info in itr
        )

    def _compute_theodata(self, _: pd.DataFrame) -> pd.DataFrame:
        return pd.DataFrame({i: j[:0] for i, j in self._theodata.data.items()})
