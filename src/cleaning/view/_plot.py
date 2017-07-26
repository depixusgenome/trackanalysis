#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Cycles plot view for cleaning data"
from    typing         import Dict, TYPE_CHECKING

from    bokeh.plotting import figure, Figure
from    bokeh.models   import LinearAxis, ColumnDataSource, Range1d
from    bokeh          import layouts
import  bokeh.colors

import  numpy                   as     np

from    utils.array             import repeat
from    view.plots              import PlotAttrs, PlotView
from    view.plots.tasks        import TaskPlotCreator
from    control                 import Controller

from    ._model                 import DataCleaningModelAccess
from    ._widget                import WidgetMixin
from    ..processor             import DataCleaningProcessor, DataCleaning

class GuiDataCleaningProcessor(DataCleaningProcessor):
    "gui data cleaning processor"
    tasktype = DataCleaningProcessor.tasktype
    @classmethod
    def compute(cls, frame, info, cache = None, **cnf):
        "returns the result of the beadselection"
        cpy = np.copy(info[1])
        super().compute(frame, (info[0], cpy), cache = cache, **cnf)
        DataCleaning(**cnf).aberrant(info[1], clip = True)
        cache['gui'] = np.isnan(cpy)
        return None

    @staticmethod
    def nans(mdl, nans):
        "returns an array with nan positions per cycle"
        return np.array(list(mdl.track.cycles.withdata({0:nans}).values()), dtype = 'O')

    @staticmethod
    def runbead(mdl):
        "updates the cache in the gui and returns the nans"
        ctrl = mdl.processors(GuiDataCleaningProcessor)
        if ctrl is None:
            cycles = None
        else:
            cycles = next(iter(ctrl.run(copy = True)))[mdl.bead, ...]
        items  = None if cycles is None else list(cycles)

        tsk    = mdl.cleaning.task
        cache  = ctrl.data.getCache(tsk)()
        nans   = cache.pop('gui')
        mdl.processors().data.setCacheDefault(tsk, {}).update(cache)
        return items, nans

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
                      population = 'hotpink',
                      aberrant   = 'gold')
        cnf.colors.basic.defaults = colors
        cnf.colors.dark .defaults = colors
        cnf.colors.order.default  = ('good', 'hfsigma', 'extent', 'population', 'aberrant')

        self.css.figure.width.default  = 500

        self.__source: ColumnDataSource = None
        self.__fig:    Figure           = None
        if TYPE_CHECKING:
            self._model = DataCleaningModelAccess(self._ctrl, '')

    def _create(self, doc):
        self.__source = ColumnDataSource(data = self.__data(None, None))

        self.__fig = fig = figure(**self._figargs(y_range = Range1d,
                                                  x_range = Range1d,
                                                  name    = 'Clean:Cycles'))
        self.css.points.addto(fig, x = 't', y = 'z', source = self.__source)
        fig.extra_x_ranges = {"time": Range1d(start = 0., end = 0.)}
        axis = LinearAxis(x_range_name = "time", axis_label = self.css.xtoplabel.get())
        fig.add_layout(axis, 'above')

        self.fixreset(fig.y_range)
        self._addcallbacks(fig)

        mode    = self.defaultsizingmode()
        widgets = self._createwidget(fig)
        bottom  = layouts.widgetbox(widgets['align'], **mode)
        left    = layouts.widgetbox(widgets['cleaning']+widgets['table'], **mode)
        return self._keyedlayout(fig, left = left, bottom = bottom)

    def _reset(self):
        items, nans = GuiDataCleaningProcessor.runbead(self._model)
        data                                  = self.__data(items, nans)
        self._bkmodels[self.__source]['data'] = data
        self.setbounds(self.__fig.x_range, 'x', data['t'])
        self.setbounds(self.__fig.y_range, 'y', data['z'])
        self._resetwidget()

    def __data(self, items, nans) -> Dict[str, np.ndarray]:
        if items is None or len(items) == 0 or not any(len(i) for _, i in items):
            items = [((0,0), [])]

        bad   = self._model.cleaning.badcycles()
        order = np.array(sorted(range(len(items)), key = lambda i: (i not in bad, i)),
                         dtype = 'i4')

        size  = max(len(i) for _, i in items)
        val   = np.full((len(items), size), np.NaN, dtype = 'f4')
        for (_, i), j in items:
            val[order[i],:len(j)] = j

        res = dict(t     = repeat(range(val.shape[1]), val.shape[0], 0),
                   z     = val.ravel(),
                   cycle = repeat([i[-1] for i, _ in items], val.shape[1], 1),
                   color = self.__color(order, nans, val))
        assert all(len(i) == val.size for  i in res.values())
        return res

    def __color(self, order, nancache, items) -> np.ndarray:
        colors = self.css.colors[self.css.theme.get()].getitems(...)
        hexes  = {i: getattr(bokeh.colors, j).to_hex() for i, j in colors.items()}

        tmp    = np.full(items.shape, hexes['good'], dtype = '<U7')
        cache  = self._model.cleaning.cache
        for name in self.css.colors.order.get():
            if name == 'aberrant' and nancache is not None:
                color   = hexes[name]
                cycnans = GuiDataCleaningProcessor.nans(self._model, nancache)[order]
                for cyc, nans in enumerate(cycnans):
                    tmp[cyc,:len(nans)][nans] = color

            elif cache is not None:
                value, color = cache.get(name, None), hexes[name]
                if value is not None:
                    tmp[order[value.min]] = color
                    tmp[order[value.max]] = color
        return tmp.ravel()

class CleaningView(PlotView):
    "Peaks plot view"
    PLOTTER = CleaningPlotCreator
    def ismain(self):
        "Cleaning and alignment, ... are set-up by default"
        super()._ismain(tasks  = ['datacleaning', 'extremumalignment'],
                        ioopen = [slice(None, -2),
                                  'control.taskio.ConfigGrFilesIO',
                                  'control.taskio.ConfigTrackIO'])
