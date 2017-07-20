#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Cycles plot view for cleaning data"
from    typing         import Dict, TYPE_CHECKING

from    bokeh.plotting import figure, Figure
from    bokeh.models   import LinearAxis, ColumnDataSource, Range1d
from    bokeh          import layouts
import  bokeh.colors

import  numpy                   as     np
from    numpy.lib.index_tricks  import as_strided

from    view.plots              import PlotAttrs, PlotView
from    view.plots.tasks        import TaskPlotCreator
from    control                 import Controller

from    ._model                 import DataCleaningModelAccess
from    ._widget                import WidgetMixin
from    ..processor             import DataCleaningException

class CleaningPlotCreator(TaskPlotCreator, WidgetMixin):
    "Building the graph of cycles"
    _MODEL = DataCleaningModelAccess
    def __init__(self,  ctrl:Controller) -> None:
        "sets up this plotter's info"
        super().__init__(ctrl)
        WidgetMixin.__init__(self)
        cnf = self.css
        cnf.plot.figure.height.default = self.css.plot.figure.width.get()//2
        cnf.points.default  = PlotAttrs('color',  'circle', 1, alpha   = .5)

        colors = dict(good       = 'blue',
                      hfsigma    = 'red',
                      extent     = 'orange',
                      population = 'hotpink')
        cnf.colors.basic.defaults = colors
        colors['good'] = 'gray'
        cnf.colors.dark .defaults = colors

        self.css.figure.width.default  = 500

        self.__source: ColumnDataSource = None
        self.__fig:    Figure           = None
        if TYPE_CHECKING:
            self._model = DataCleaningModelAccess(self._ctrl, '')

    def _create(self, doc):
        self.__source = ColumnDataSource(data = self.__data())

        self.__fig = fig = figure(**self._figargs(y_range = Range1d, name = 'Clean:Cycles'))
        self.css.points.addto(fig, x = 't', y = 'z', source = self.__source)
        fig.extra_x_ranges = {"time": Range1d(start = 0., end = 0.)}
        axis = LinearAxis(x_range_name = "time", axis_label = self.css.xtoplabel.get())
        fig.add_layout(axis, 'above')

        self._addcallbacks(fig)
        mode    = self.defaultsizingmode()
        widgets = self._createwidget(fig)
        bottom  = layouts.widgetbox(widgets['align'], **mode)
        left    = layouts.widgetbox(widgets['cleaning']+widgets['table'], **mode)
        col     = layouts.column([self._keyedlayout(fig), bottom], **mode)
        return layouts.row([left, col], **mode)

    def _reset(self):
        if self._model.colorstore is not None:
            color = self.__color()
            if not np.all_close(color, self.__source.data['color']):
                self.__source.stream(dict(color = color), rollover = len(color))
        else:
            data                                  = self.__data()
            self._bkmodels[self.__source]['data'] = data
            self.setbounds(self.__fig.y_range, 'y', data['z'])
        self._resetwidget()

    def __data(self) -> Dict[str, np.ndarray]:
        cycles = self._model.runbead()
        if cycles is None:
            items = None
        else:
            try:
                items = list(cycles)
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

    def __color(self, items = None, val = None) -> np.ndarray:
        assert (val is None) is (items is None)
        if items is not None:
            self._model.colorstore = np.argsort([i[-1] for i, _ in items]), val.shape
        inds, shape = self._model.colorstore

        cnf   = self.css.colors[self.css.theme.get()]
        hexes = {i: getattr(bokeh.colors, cnf[i].get()).to_hex()
                 for i in ('good', 'hfsigma', 'extent', 'population')}

        tmp   = np.full(len(inds), hexes['good'], dtype = '<U7')
        cache = self._model.cleaning.cache
        for name, value in () if cache is None else cache.items():
            tmp[inds[value.min]] = hexes[name]
            tmp[inds[value.max]] = hexes[name]

        return as_strided(tmp, shape = shape, strides = (tmp.strides[0], 0))

class CleaningView(PlotView):
    "Peaks plot view"
    PLOTTER = CleaningPlotCreator
    def ismain(self):
        "Cleaning and alignment, ... are set-up by default"
        super()._ismain(tasks  = ['datacleaning', 'extremumalignment'],
                        ioopen = [slice(None, -2),
                                  'control.taskio.ConfigGrFilesIO',
                                  'control.taskio.ConfigTrackIO'])
