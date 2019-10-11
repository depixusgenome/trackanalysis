#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"View module showing one or more FoVs"
from   abc                     import abstractmethod, ABC
from   copy                    import copy
from   functools               import partial
from   importlib               import import_module
from   threading               import Lock
from   typing                  import (
    Dict, List, Iterator, Tuple, Optional, Union, Set, cast
)

import pandas as pd
import numpy  as np

from   bokeh                   import layouts
from   bokeh.models            import ColumnDataSource, FactorRange
from   bokeh.plotting          import figure, Figure

from   taskmodel               import RootTask
from   taskmodel.processors    import TaskCacheList
from   taskmodel.dataframe     import DataFrameTask
from   taskmodel.application   import setupio
from   view.colors             import tohex
from   view.threaded           import ThreadedDisplay, DisplayModel
from   ._model                 import (
    BeadsScatterPlotStatus, BeadsScatterPlotConfig, TasksModelController, STORE
)
from   ._widgets               import JobsStatusBar, JobsHairpinSelect


# make sure all configs are loaded
def _import():
    for i in ('cleaning', 'eventdetection', 'peakfinding', 'peakcalling'):
        import_module(f'{i}.processor.__config__')


_import()
del _import

class BeadsScatterPlotModel(DisplayModel[BeadsScatterPlotStatus, BeadsScatterPlotConfig]):
    "model for display the FoVs"
    tasks: TasksModelController

    def __init__(self, **_):
        super().__init__()
        self.tasks = TasksModelController()

class BeadsScatterPlot(ThreadedDisplay[BeadsScatterPlotModel]):
    "display the current bead"
    _fig:         Figure
    _expdata:     ColumnDataSource
    _defaultdata: Dict[str, list]
    _theodata:    ColumnDataSource

    def __init__(self, **_):
        super().__init__(**_)
        self._widgets  = (JobsStatusBar(), JobsHairpinSelect())
        self._threader = _Threader(self)

    def swapmodels(self, ctrl):
        "swap with models in the controller"
        super().swapmodels(ctrl)
        for i in self._widgets:
            if hasattr(i, 'swapmodels'):
                i.swapmodels(ctrl)

    def ismain(self, ctrl):
        "Set-up things if this view is the main one"

        setupio(
            ctrl,
            (
                'datacleaning', 'extremumalignment', 'clipping',
                'eventdetection', 'peakselector', 'singlestrand',
                'baselinepeakfilter'
            ),
            ioopen = (
                slice(None, -2),
                'hybridstat.view._io.PeaksConfigGRFilesIO',
                'hybridstat.view._io.PeaksConfigMuWellsFilesIO',
                'hybridstat.view._io.PeaksConfigTrackIO',
            )
        )

    def observe(self, ctrl):
        """observe the controller"""
        self._model.observe(ctrl)

        ctrl.display.observe(
            self._model.display,
            partial(self._threader.mask, ctrl)
        )
        ctrl.display.observe(
            self._model.tasks.eventjobstop,
            partial(self._threader.mask, ctrl)
        )
        ctrl.display.observe(
            self._model.tasks.eventname,
            partial(self._threader.update, ctrl)
        )

        for i in self._widgets:
            if hasattr(i, 'observe'):
                i.observe(ctrl, self._model.tasks)

    def _addtodoc(self, ctrl, doc):
        "sets the plot up"
        self._addtodoc_data()
        self._addtodoc_fig()
        itms      = [i.addtodoc(ctrl, doc)[0] for i in self._widgets]
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

    def _reset(self, ctrl, cache):
        "resets the plot"
        self._threader.reset(cache)

    def _addtodoc_data(self):
        self._defaultdata  = dict(
            {i: [''] for i in  ('hairpin', 'status')},
            color = ['green'],
            **{
                i: [0.]
                for i in  (
                    'bead', 'hybridisationrate', 'baseposition', 'peakposition',
                    'closest', 'cost', 'trackid'
                )
            },
            x = [('track1', '0')]
        )
        self._expdata  = ColumnDataSource(self._defaultdata)
        self._theodata = ColumnDataSource(dict(
            {i: [''] for i in  ('hairpin', 'status', 'color')},
            bindingposition = [0],
            x               = [('track1', '0')]
        ))

    def _addtodoc_fig(self):
        "build a figure"
        fig = figure(
            **self._model.theme.figargs,
            x_range          = FactorRange(factors = self._expdata.data['x']),
        )
        self.attrs(self._model.theme.events).addto(fig, source = self._expdata)
        self.attrs(self._model.theme.blockages).addto(fig, source = self._expdata)
        self.attrs(self._model.theme.bindings).addto(fig, source = self._theodata)
        self._fig = fig

class _Threader:
    """
    In charge of thread safety & deciding whether to reset or update the plots
    """
    plot: '_Plot'

    def __init__(self, view):
        self.view        = view
        self.idval: int  = -1
        self.lock:  Lock = Lock()

    def reset(self, cache):
        "runs the first reset"
        idval = -2
        with self.lock:
            idval = self.idval
            if hasattr(self, 'plot'):
                del self.plot
        self._run(idval, cache)

    def update(self, ctrl, idval, **_):
        "calls an update"
        with self.lock:
            if self.idval != idval and hasattr(self, 'plot'):
                del self.plot
            self.idval = idval

            self.view.reset(ctrl, fcn = partial(self._run, idval))

    def mask(self, ctrl, **_):
        "action on mask"
        with self.lock:
            if hasattr(self, 'plot'):
                del self.plot
            self.view.reset(ctrl, fcn = partial(self._run, self.idval))

    def _run(self, idval, cache):
        "runs the display"
        if self.idval == idval:
            plot = None
            cpy  = None

            with self.lock:
                plot = getattr(self, 'plot', None)
                if self.idval == idval and plot is None:
                    procs     = getattr(self.view, '_model').tasks.processors
                    self.plot = plot = (
                        _HairpinPlot
                        if any(
                            hasattr(j, 'sequences') for i in procs.values() for j in i.model
                        ) else
                        _PeaksPlot
                    )(self.view, procs)

                cpy = copy(plot)

            if self.idval == idval:
                try:
                    cpy.reset(cache)
                except Exception:  # pylint: disable=broad-except
                    with self.lock:
                        if hasattr(self, 'plot'):
                            del self.plot
                    raise
                else:
                    with self.lock:
                        plot.__dict__.update(cpy.__dict__)

                    if self.idval != idval:
                        cache.clear()

class _PlotDescr:
    _name: str

    def __set_name__(self, _, name: str):
        self._name = name

    def __get__(self, inst, tpe):
        return self if inst is None else getattr(inst.parent, self._name)

    def __set__(self, inst, val):
        setattr(inst.parent, self._name, val)

class _Plot(ABC):
    def __init__(self, mdl: BeadsScatterPlot, procs: Dict[RootTask, TaskCacheList]):
        self.parent:    BeadsScatterPlot                 = mdl
        self._procs:    Dict[RootTask, TaskCacheList] = procs
        self._factors:  List[Tuple[str,...]]          = []
        self._data:     pd.DataFrame                  = pd.DataFrame({})

    _expdata:     ColumnDataSource   = cast(ColumnDataSource,   _PlotDescr())
    _defaultdata: Dict[str, list]    = cast(Dict[str, list],    _PlotDescr())
    _theodata:    ColumnDataSource   = cast(ColumnDataSource,   _PlotDescr())
    _model:       BeadsScatterPlotModel = cast(BeadsScatterPlotModel, _PlotDescr())
    _fig:         Figure             = cast(Figure,             _PlotDescr())

    def reset(self, cache):
        "resets the data"
        cache.update((self._reset if self._isdefault() else self._update)())

    def _reset(self):
        "resets the data"
        data, status = self.__compute_expdata()

        if status:
            exp     = self._defaultdata
            factors = exp['x']
            theo    = {i: j[:0] for i, j in self._theodata.data.items()}
        else:
            factors = self._xfactors(data)
            exp     = self.__from_df(data)
            theo    = self.__from_df(self._compute_theodata(data))

        yield (self._expdata,      dict(data       = exp))
        yield (self._theodata,     dict(data       = theo))
        yield (self._fig.x_range,  dict(factors    = factors))
        yield (self._fig.yaxis[0], dict(axis_label = self._yaxis()))

    def _update(self):
        "streams the data"
        data, status = self.__compute_expdata()

        if status:
            return

        yield (self._fig.x_range, dict(factors = self._xfactors(data)))
        yield ('_expdata',        partial(self._expdata.stream, self.__from_df(data)))
        theo    = self._compute_theodata(data)
        if theo.shape[0]:
            yield ('_theodata',   partial(self._theodata.stream, self.__from_df(theo)))

    def _isdefault(self) -> bool:
        return not self._factors

    def __iter_cache(self) -> Iterator[Tuple[int, int, pd.DataFrame]]:
        cur: Set[Tuple[int, int]] = set(
            () if not self._data.shape[0] else
            self._data.set_index(['trackid', 'bead']).index.unique()
        )
        for iproc, proc in enumerate(self._procs.values()):
            cache: Optional[STORE] = proc.data.getcache(DataFrameTask)()
            if cache is None or self._model.display.masked(root = proc.model[0]):
                continue

            for bead,  info in dict(cache).items():
                if (
                        not isinstance(info, pd.DataFrame)
                        or info.shape[0] == 0
                        or (iproc, bead) in cur
                        or self._model.display.masked(root = proc.model[0], bead = bead)
                ):
                    continue

                info = info.reset_index()
                name = (f"{iproc}-"+info.track[0], str(bead))
                yield info.assign(trackid = iproc, x = [name]*len(info))

    def __compute_expdata(self) -> Tuple[pd.DataFrame, bool]:
        lst  = [i for i in self._compute_expdata(self.__iter_cache()) if i.shape[0]]
        if not lst:
            return pd.DataFrame(self._defaultdata), True

        colors = tohex(self._model.theme.colors)
        order  = self._model.theme.order
        frame  = (
            pd.concat(lst)
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

    @staticmethod
    def __from_df(data) -> Dict[str, np.ndarray]:
        return {i: j.values for i, j in data.items()}

    def _xfactors(self, frame: pd.DataFrame) -> Union[List[str], List[Tuple[str,...]]]:
        frame = (
            frame[['trackid', 'bead', 'x', *self._factorcols()]]
            .groupby(['trackid', 'bead'])
            .first()
            .reset_index()
        )
        assert ('track1', '0') not in self._factors
        if self._data.shape[0]:
            assert ('track1', '0') not in self._data.x.tolist()
        assert ('track1', '0') not in frame.x.tolist()
        self._data    = pd.concat([self._data,  frame]) if self._factors else frame
        self._factors = list(self._sortfactors(self._data).x)
        return self._factors

    @abstractmethod
    def _yaxis(self) -> str:
        pass

    @staticmethod
    @abstractmethod
    def _factorcols() -> List[str]:
        pass

    @staticmethod
    @abstractmethod
    def _sortfactors(data: pd.DataFrame) -> pd.DataFrame:
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

    @staticmethod
    def _sortfactors(data: pd.DataFrame) -> pd.DataFrame:
        cols = ['hairpin', 'trackid']
        return (
            data
            .set_index(cols[0])
            .join(data.groupby(cols[:1]) .cost.median().rename("hcost").to_frame())
            .set_index(cols[1], append = True)
            .join(data.groupby(cols[:2]).cost.median().rename("tcost").to_frame())
        ).sort_values(['hcost', 'tcost', 'cost'])

    @staticmethod
    def _beadorder() -> List[str]:
        return ['hairpin', 'trackid', 'cost']

    def _compute_expdata(self, itr: Iterator[pd.DataFrame]) -> Iterator[pd.DataFrame]:
        def _x(info):
            return lambda x, y = info.iloc[0].x: (x, *y)

        hpin = set(self._model.display.hairpins)
        for info in itr:
            info = (
                info
                .groupby(['trackid', 'bead'])
                .apply(lambda x: x.nsmallest(1, "cost"))
                .reset_index(drop = True)
            )

            if hpin:
                info = info[~info.hpin.apply(hpin.__contains__)]

            if info.shape[0] == 0:
                continue

            out  = (
                info.peaks[0].reset_index()
                [['hybridisationrate', 'status', 'baseposition', 'peakposition', 'closest']]
                .assign(
                    hairpin = info.iloc[0]['hpin'],
                    **{i: info.iloc[0][i] for i in ('trackid', 'bead', 'cost')}
                )
            )
            out['x'] = out.hairpin.apply(_x(info))
            yield out

    def _compute_theodata(self, expdata: pd.DataFrame) -> pd.DataFrame:
        if (
                expdata.shape[0] == 0
                or all(expdata[i].tolist() == self._defaultdata[i] for i in ('x', 'baseposition'))
        ):
            return pd.DataFrame({i: j[:0] for i, j in self._theodata.data.items()})

        hpin: Dict[Tuple[int, str], np.ndarray] = {}
        ids:  Set[int]                          = set(expdata.trackid.unique())
        for iproc, proc in enumerate(self._procs.values()):
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
        return data

class _PeaksPlot(_Plot):
    @staticmethod
    def _factorcols() -> List[str]:
        return []

    def _yaxis(self) -> str:
        return self._model.theme.yaxis[0].format(1e3/self._model.theme.stretch)

    @staticmethod
    def _sortfactors(data: pd.DataFrame) -> Tuple[List[str], List[str]]:
        return data.sort_values(['trackid', 'bead'])

    @staticmethod
    def _beadorder() -> List[str]:
        return ['trackid', 'bead']

    def _compute_expdata(self, itr: Iterator[pd.DataFrame]) -> Iterator[pd.DataFrame]:
        return (
            info
            [['trackid','bead', 'x', 'hybridisationrate', 'status', 'peakposition']]
            .assign(baseposition = lambda x: x.peakposition * self._model.theme.stretch)
            for info in itr
        )

    def _compute_theodata(self, _: pd.DataFrame) -> pd.DataFrame:
        return pd.DataFrame({i: j[:0] for i, j in self._theodata.data.items()})
