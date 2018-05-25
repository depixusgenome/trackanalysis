#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Cycles plot"
from    typing              import TYPE_CHECKING
from    bokeh               import layouts

from    control             import Controller
from    control.taskio      import ConfigTrackIO, GrFilesIO

from    view.plots          import PlotView, CACHE_TYPE
from    view.plots.tasks    import TaskPlotCreator

from   ._bokehext           import DpxHoverModel
from   ._model              import CyclesModelAccess, CyclesPlotModel
from   ._raw                import RawMixin
from   ._hist               import HistMixin
from   ._widget             import WidgetMixin

class CyclesPlotCreator(TaskPlotCreator[CyclesModelAccess, CyclesPlotModel], # type: ignore
                        HistMixin, RawMixin, WidgetMixin):
    "Displays cycles and their projection"
    _model: CyclesModelAccess
    _hover: DpxHoverModel
    def __init__(self, ctrl:Controller) -> None:
        "sets up this plotter's info"
        super().__init__(ctrl, noerase = False)
        RawMixin   .__init__(self)
        HistMixin  .__init__(self, ctrl)
        WidgetMixin.__init__(self, ctrl, self._model)

    def _addtodoc(self, ctrl, doc):
        "returns the figure"
        fcn = lambda attr, old, new: self._model.newparams(**{attr: new})
        self._hover.on_change("stretch", fcn)
        self._hover.on_change("bias",    fcn)

        doc.add_root(self._hover)

        shape = self._createraw()
        self._createhist(self._rawsource.data, shape, self._raw.y_range)
        if 'fixed' in self.defaultsizingmode().values():
            return [self._keyedlayout(ctrl, self._raw, self._hist),
                    self._createwidget(ctrl, doc)]
        return [self._createwidget(ctrl, doc), self._keyedlayout(ctrl, self._raw, self._hist)]

    def _reset(self, cache: CACHE_TYPE):
        shape = self._DEFAULT_DATA[1]
        try:
            shape = self._resetraw(cache)
        finally:
            data  = cache[self._rawsource]['data']
            self._resethist(cache, data, shape)
            self._resetwidget(cache)

    def ismain(self, ctrl):
        WidgetMixin.ismain(self, ctrl)

    def observe(self, ctrl):
        "sets-up model observers"
        super().observe(ctrl)
        self._histobservers(ctrl)
        self._widgetobservers(ctrl)
        ctrl.theme.observe(self._model.cycles.theme,  lambda **_: self.reset(False))
        ctrl.theme.observe(self._model.cycles.config, lambda **_: self.reset(False))

class CyclesPlotView(PlotView[CyclesPlotCreator]):
    "Cycles plot view"
    APPNAME = 'cyclesplot'
    TASKS   = 'extremumalignment', 'eventdetection'
    def advanced(self):
        "triggers the advanced dialog"
        self._plotter.advanced()

    def ismain(self, ctrl):
        "Alignment, ... is set-up by default"
        self._ismain(ctrl, tasks = self.TASKS)
