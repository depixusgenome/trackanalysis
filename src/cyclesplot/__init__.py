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
        WidgetMixin    .__init__(self, ctrl)

        DpxHoverModel.defaultconfig(self)
        self.css.tools.default  = 'ypan,ybox_zoom,reset,save,dpxhover'
        self._hover: DpxHoverModel = None

        if TYPE_CHECKING:
            self._model = CyclesModelAccess('', '')

    def _addtodoc(self, ctrl, doc):
        "returns the figure"
        self._hover = DpxHoverModel()
        doc.add_root(self._hover)

        shape = self._createraw()
        self._createhist(self._rawsource.data, shape, self._raw.y_range)
        if 'fixed' in self.defaultsizingmode().values():
            layout = [self._keyedlayout(ctrl, self._raw, self._hist), self._createwidget()]
        layout = [self._createwidget(), self._keyedlayout(ctrl, self._raw, self._hist)]
        self._histobservers()
        self._widgetobservers(ctrl)
        return layout

    def _reset(self):
        shape = self._DEFAULT_DATA[1]
        try:
            shape = self._resetraw()
        finally:
            data  = self._bkmodels[self._rawsource]['data']
            self._resethist(data, shape)
            self._resetwidget()

    def ismain(self, ctrl):
        WidgetMixin.ismain(self, ctrl)

    def observe(self, ctrl):
        "sets-up model observers"
        super().observe(ctrl)
        self._model.config.observe('eventdetection.isactive', 'binwidth', 'minframes',
                                   lambda: self.reset(False))

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
