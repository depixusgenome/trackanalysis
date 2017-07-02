#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Cycles plot view for cleaning data"
from    typing         import Dict, Tuple, TYPE_CHECKING #pylint: disable=unused-import

from    bokeh.plotting import figure, Figure # pylint: disable=unused-import
from    bokeh.models   import LinearAxis, ColumnDataSource, Range1d
import  bokeh.colors

import  numpy                   as     np
from    numpy.lib.index_tricks  import as_strided

from    view.plots              import PlotAttrs, PlotView
from    view.plots.tasks        import TaskPlotCreator
from    control                 import Controller

from    ._model                 import DataCleaningModelAccess
from    ..processor             import DataCleaningException

class DataCleaningPlotCreator(TaskPlotCreator):
    "Building the graph of cycles"
    _MODEL = DataCleaningModelAccess
    def __init__(self,  ctrl:Controller) -> None:
        "sets up this plotter's info"
        super().__init__(ctrl)
        cnf = self.css.cycles
        cnf.points      .default  = PlotAttrs('color',  'circle', 1, alpha   = .5)
        cnf.colors.basic.defaults = dict(good = 'blue', bad = 'red', extent = 'orange')
        cnf.colors.dark .defaults = dict(good = 'gray', bad = 'red', extent = 'orange')
        self.css.figure.width.default  = 500

        self.__source  = None                 # type: ColumnDataSource
        self.__store   = (np.ones(0), (0, 0)) # type: Tuple[np.ndarray, Tuple[int,...]]
        if TYPE_CHECKING:
            self._model = DataCleaningModelAccess(self._ctrl, '')

    def _create(self, doc):
        self.__source = ColumnDataSource(data = self.__data())

        fig            = figure(**self._figargs(y_range = Range1d, name = 'Clean:Cycles'))
        self.css.cycles.points.addto(fig, x = 't', y = 'z', source = self.__source)
        fig.extra_x_ranges = {"time": Range1d(start = 0., end = 0.)}
        axis = LinearAxis(x_range_name = "time", axis_label = self.css.xtoplabel.get())
        fig.add_layout(axis, 'above')

        self._addcallbacks(fig)
        self._createwidget(fig)
        return self.__model.figure

    def _reset(self):
        self._bkmodels[self.__source]['data']      = self.__data()

        info = dict(framerate = getattr(self._model.track, 'framerate', 1./30.))
        task = self._model.cleaning.task
        if task is not None:
            info.update(task.config())

    def __data(self) -> Dict[str, np.ndarray]:
        try:
            items = list(self._model.runbead())
        except DataCleaningException:
            items = None

        if items is None or len(items) == 0 or not any(len(i) for _, i in items):
            items = [((0,0), [])]

        val = self.__zvalue(items)
        res = dict(t     = self.__time(val).ravel(),
                   z     = val.ravel(),
                   cycle = self.__cycle(items, val).ravel(),
                   color = self.__color(items, val).ravel())
        assert all(len(i) == val.size for  i in res.values())
        return res

    def __ondatacleaning(self):
        color = self.__update_color(**self.__store)
        if any(i != j for i, j in zip(color, self.__source.data['color'])):
            self.__source.stream(dict(color = color), rollover = len(color))

    @staticmethod
    def __zvalue(items) -> np.ndarray:
        size = max(len(i) for _, i in items)
        val  = np.full((len(items), size), np.NaN, dtype = 'f4')
        for i, (_, j) in zip(val, items):
            i[:len(j)] = j
        return val

    @staticmethod
    def __time(val) -> np.ndarray:
        tmp   = np.arange(val.size, dtype = 'i4')
        return as_strided(tmp, shape = val.shape, strides = (0, tmp.strides[0]))

    @staticmethod
    def __cycle(items, val) -> np.ndarray:
        tmp = np.array([i[-1] for i, _ in items], dtype = 'i4')
        return as_strided(tmp, shape = val.shape, strides = (tmp.strides[0], 0))

    def __color(self, items, val) -> np.ndarray:
        self.__store = np.argsort([i[-1] for i, _ in items]), val.shape
        return self.__update_color(*self.__store)

    def __update_color(self, inds, shape) -> np.ndarray:
        cnf   = self.css.colors[self.css.theme.get()]
        hexes = {i: getattr(bokeh.colors, cnf[i].get()).to_hex()
                 for i in ('good', 'hfsigma', 'extent')}

        tmp   = np.full(len(inds), hexes['good'], dtype = '<U7')
        cache = self._model.cleaning.cache
        for name, value in () if cache is None else cache.items():
            tmp[inds[value.low ]] = hexes[name]
            tmp[inds[value.high]] = hexes[name]

        return as_strided(tmp, shape = shape, strides = (tmp.strides[0], 0))

class DataCleaningPlotView(PlotView):
    "Peaks plot view"
    PLOTTER = DataCleaningPlotCreator
    def ismain(self):
        "Alignment, ... is set-up by default"
        raise NotImplementedError()
