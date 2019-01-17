#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Cycles plot"
from    typing               import TYPE_CHECKING
from    bokeh                import layouts

from    taskcontrol.taskio   import ConfigTrackIO, GrFilesIO
from    taskview.plots       import PlotView, CACHE_TYPE, TaskPlotCreator
from   ._bokehext            import DpxHoverModel
from   ._model               import CyclesModelAccess, CyclesPlotModel
from   ._raw                 import RawMixin
from   ._hist                import HistMixin
from   ._widget              import WidgetMixin

class CyclesPlotCreator( # pylint: disable=too-many-ancestors
        TaskPlotCreator[CyclesModelAccess, CyclesPlotModel], # type: ignore
        HistMixin, RawMixin, WidgetMixin
):
    "Displays cycles and their projection"
    _model: CyclesModelAccess
    _hover: DpxHoverModel
    def __init__(self, ctrl) -> None:
        "sets up this plotter's info"
        super().__init__(ctrl, noerase = False)
        RawMixin   .__init__(self)
        HistMixin  .__init__(self, ctrl)
        WidgetMixin.__init__(self, ctrl, self._model)

    def _addtodoc(self, ctrl, doc, *_):
        "returns the figure"
        shape = self._createraw()
        self._createhist(doc, self._rawsource.data, shape, self._raw.y_range)
        self._finishraw(shape)
        parent  = self._keyedlayout(ctrl, self._raw, self._hist)
        widgets = self._createwidget(ctrl)
        if 'fixed' in self.defaultsizingmode().values():
            return [parent, widgets]
        return [widgets, parent]

    def _reset(self, cache: CACHE_TYPE):
        shape, disable = self._DEFAULT_DATA[1], True
        try:
            shape, disable = self._resetraw(cache), False
        finally:
            data  = cache[self._rawsource]['data']
            self._resethist(cache, data, shape)
            self._resetwidget(cache, disable)

    def ismain(self, ctrl):
        WidgetMixin.ismain(self, ctrl)

    def observe(self, ctrl, noerase = True):
        "sets-up model observers"
        super().observe(ctrl, noerase)
        self._histobservers(ctrl)
        self._widgetobservers(ctrl)
        ctrl.theme.observe(self._model.cycles.theme,  lambda **_: self.reset(False))
        ctrl.theme.observe(self._model.cycles.config, lambda **_: self.reset(False))

        def _onchangefig(old = None, **_):
            if 'figsize' in old:
                @self.calllater
                def _cb():
                    theme = self._theme.figsize
                    self._raw .plot_width  = theme[0]
                    self._raw .plot_height = theme[1]
                    self._hist.plot_width  = theme[0]
                    self._hist.plot_height = theme[1]
                    self._raw.trigger("sizing_mode", theme[-1], theme[-1])
                    self._hist.trigger("sizing_mode", theme[-1], theme[-1])

        ctrl.theme.observe(self._theme, _onchangefig)

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
