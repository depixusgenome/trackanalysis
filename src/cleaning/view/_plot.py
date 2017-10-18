#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Cycles plot view for cleaning data"
from    typing         import Dict, TYPE_CHECKING

from    bokeh.plotting import figure, Figure
from    bokeh.models   import LinearAxis, ColumnDataSource, Range1d
from    bokeh          import layouts
from    bokeh.colors   import named as _bkclr

import  numpy                   as     np

from    utils.array             import repeat
from    view.plots              import PlotAttrs, PlotView, DpxHoverTool
from    view.plots.tasks        import TaskPlotCreator
from    control                 import Controller

from    ._model                 import DataCleaningModelAccess
from    ._widget                import WidgetMixin
from    ..processor             import DataCleaningProcessor, DataCleaning

class GuiDataCleaningProcessor(DataCleaningProcessor):
    "gui data cleaning processor"
    @staticmethod
    def canregister():
        "allows discarding some specific processors from automatic registration"
        return False

    @classmethod
    def compute(cls, frame, info, cache = None, **cnf):
        "returns the result of the beadselection"
        curr = np.copy(info[1])
        super().compute(frame, (info[0], curr), cache = cache, **cnf)
        DataCleaning(**cnf).aberrant(info[1], clip = True)
        cache['gui'] = np.isnan(curr)
        return None

    @staticmethod
    def nans(mdl, nans):
        "returns an array with nan positions per cycle"
        if nans is None:
            return ()
        return (np.asarray(i, dtype = 'bool')
                for i in mdl.track.cycles.withdata({0:nans}).values())

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
        if tsk is None:
            return items, None

        cache  = ctrl.data.getCache(tsk)()
        nans   = cache.pop('gui', None)
        mdl.processors().data.setCacheDefault(tsk, {}).update(cache)
        return items, nans

class CleaningPlotCreator(TaskPlotCreator[DataCleaningModelAccess], WidgetMixin):
    "Building the graph of cycles"
    def __init__(self,  ctrl:Controller) -> None:
        "sets up this plotter's info"
        super().__init__(ctrl)
        WidgetMixin.__init__(self)
        cnf = self.css
        cnf.plot.figure.height.default = self.css.plot.figure.width.get()//2
        cnf.plot.figure.defaults  = {'width': 500, 'height': 800}
        cnf.points.default  = PlotAttrs('color',  'circle', 1, alpha   = .5)

        colors = dict(good       = '#6baed6', # blue
                      hfsigma    = 'gold',
                      extent     = 'orange',
                      population = 'hotpink',
                      aberrant   = 'red')
        cnf.colors.basic.defaults = colors
        cnf.colors.dark .defaults = colors
        cnf.colors.order.default  = ('aberrant', 'hfsigma', 'extent', 'population', 'good')
        self.css.widgets.width.default = 400
        self.css.figure.defaults  = dict(width    = 600,
                                         height   = 800,
                                         tooltips = [(u'(cycle, t, z)',
                                                      '(@cycle, $~x{1}, $data_y{1.1111})')])

        self.__source: ColumnDataSource = None
        self.__fig:    Figure           = None
        if TYPE_CHECKING:
            self._model = DataCleaningModelAccess(self._ctrl, '')

    def _create(self, _):
        self.__source = ColumnDataSource(data = self.__data(None, None))

        self.__fig = fig = figure(**self._figargs(y_range = Range1d,
                                                  x_range = Range1d,
                                                  name    = 'Clean:Cycles'))
        glyph = self.css.points.addto(fig, x = 't', y = 'z', source = self.__source)
        hover = fig.select(DpxHoverTool)
        if hover:
            hover[0].tooltips  = self.css.figure.tooltips.get()
            hover[0].renderers = [glyph]

        fig.extra_x_ranges = {"time": Range1d(start = 0., end = 0.)}
        axis = LinearAxis(x_range_name = "time", axis_label = self.css.xtoplabel.get())
        fig.add_layout(axis, 'above')

        self.fixreset(fig.y_range)
        self._addcallbacks(fig)

        mode    = self.defaultsizingmode(width = self.css.widgets.width.get())
        widgets = self._createwidget(fig)
        bottom  = layouts.widgetbox(widgets['align'], **mode)
        left    = layouts.widgetbox(widgets['cleaning']+widgets['table'], **mode)
        return self._keyedlayout(fig, left = left, bottom = bottom)

    def _reset(self):
        items, nans = GuiDataCleaningProcessor.runbead(self._model)
        data        = self.__data(items, nans)
        self._bkmodels[self.__source]['data'] = data
        self.setbounds(self.__fig.x_range, 'x', data['t'])
        self.setbounds(self.__fig.y_range, 'y', data['z'])
        self._resetwidget()

    def __data(self, items, nans) -> Dict[str, np.ndarray]:
        if items is None or len(items) == 0 or not any(len(i) for _, i in items):
            items = [((0,0), [])]

        order = self._model.cleaning.sorted(self.css.colors.order.get())
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
        tohex  = lambda clr: clr if clr[0] == '#' else getattr(_bkclr, clr).to_hex()
        hexes  = {i: tohex(j) for i, j in colors.items()}

        tmp    = np.full(items.shape, hexes['good'], dtype = '<U7')
        cache  = self._model.cleaning.cache
        for name in self.css.colors.order.get():
            if name == 'aberrant' and nancache is not None:
                color   = hexes[name]
                cycnans = GuiDataCleaningProcessor.nans(self._model, nancache)
                for cyc, nans in enumerate(cycnans):
                    tmp[order[cyc],:len(nans)][nans] = color

            elif cache is not None:
                value, color = cache.get(name, None), hexes[name]
                if value is not None:
                    tmp[order[value.min]] = color
                    tmp[order[value.max]] = color
        return tmp.ravel()

class CleaningView(PlotView[CleaningPlotCreator]):
    "Peaks plot view"
    def ismain(self):
        "Cleaning and alignment, ... are set-up by default"
        super()._ismain(tasks  = ['datacleaning', 'extremumalignment'],
                        ioopen = [slice(None, -2),
                                  'control.taskio.ConfigGrFilesIO',
                                  'control.taskio.ConfigTrackIO'])
