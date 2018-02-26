#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Cycles plot"
from    typing              import TYPE_CHECKING
from    bokeh               import layouts

from    control             import Controller
from    control.taskio      import ConfigTrackIO, GrFilesIO

from    view.plots          import PlotView
from    view.plots.tasks    import TaskPlotCreator

from   ._bokehext           import DpxHoverModel
from   ._model              import CyclesModelAccess
from   ._raw                import RawMixin
from   ._hist               import HistMixin
from   ._widget             import WidgetMixin

class CyclesPlotCreator(TaskPlotCreator[CyclesModelAccess], HistMixin, RawMixin, WidgetMixin):
    "Displays cycles and their projection"
    def __init__(self, ctrl:Controller) -> None:
        "sets up this plotter's info"
        super().__init__(ctrl)
        RawMixin       .__init__(self)
        HistMixin      .__init__(self)
        WidgetMixin    .__init__(self)

        DpxHoverModel.defaultconfig(self)
        self.css.tools.default  = 'ypan,ybox_zoom,reset,save,dpxhover'
        self._hover: DpxHoverModel = None

        if TYPE_CHECKING:
            self._model = CyclesModelAccess('', '')

    def _create(self, doc):
        "returns the figure"
        self._hover = DpxHoverModel()
        doc.add_root(self._hover)

        shape = self._createraw()
        self._createhist(self._rawsource.data, shape, self._raw.y_range)
        if 'fixed' in self.defaultsizingmode().values():
            return [self._keyedlayout(self._raw, self._hist), self._createwidget()]
        return [self._createwidget(), self._keyedlayout(self._raw, self._hist)]

    def _reset(self):
        shape = self._DEFAULT_DATA[1]
        try:
            shape = self._resetraw()
        finally:
            data  = self._bkmodels[self._rawsource]['data']
            self._resethist(data, shape)
            self._resetwidget()

    def ismain(self, _):
        WidgetMixin.ismain(self, _)

    def observe(self):
        "sets-up model observers"
        super().observe()
        self._histobservers()
        self._widgetobservers()
        self._model.config.observe('eventdetection.isactive', 'binwidth', 'minframes',
                                   lambda: self.reset(False))

class CyclesPlotView(PlotView[CyclesPlotCreator]):
    "Cycles plot view"
    APPNAME = 'cyclesplot'
    TASKS   = 'extremumalignment', 'eventdetection'
    def advanced(self):
        "triggers the advanced dialog"
        self._plotter.advanced()

    def ismain(self):
        "Alignment, ... is set-up by default"
        self._ismain(tasks = self.TASKS)
