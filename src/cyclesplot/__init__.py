#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Cycles plot"
from    typing              import Optional, TYPE_CHECKING # pylint: disable=unused-import

from    control             import Controller
from    control.taskio      import ConfigTrackIO, GrFilesIO

from    view.plots          import PlotView
from    view.plots.tasks    import TaskPlotCreator

from   ._bokehext           import DpxHoverModel
from   ._model              import CyclesModelAccess
from   ._raw                import RawMixin
from   ._hist               import HistMixin
from   ._widget             import WidgetMixin

class CyclesPlotCreator(TaskPlotCreator, HistMixin, RawMixin, WidgetMixin):
    "Displays cycles and their projection"
    _MODEL = CyclesModelAccess
    def __init__(self, ctrl:Controller) -> None:
        "sets up this plotter's info"
        TaskPlotCreator.__init__(self, ctrl)
        RawMixin       .__init__(self)
        HistMixin      .__init__(self)
        WidgetMixin    .__init__(self)

        DpxHoverModel.defaultconfig(self)
        self.config.tools.default = 'ypan,ybox_zoom,reset,save,dpxhover'
        self._hover  = None # type: Optional[DpxHoverModel]
        if TYPE_CHECKING:
            self._model = CyclesModelAccess('', '')

    def _create(self, doc):
        "returns the figure"
        self._hover = DpxHoverModel()
        doc.add_root(self._hover)
        self._createhist(self._rawsource.data, self._createraw(), self._raw.y_range)
        return self._keyedlayout(self._raw, self._hist, bottom = self._createwidget())

    def _reset(self):
        shape = self._resetraw()
        data  = self._bkmodels[self._rawsource]['data']
        self._resethist(data, shape)
        self.setbounds(self._hist.y_range, 'y', data['z'])
        self._resetwidget()

    def ismain(self, keypressmanager):
        WidgetMixin.ismain(self, keypressmanager)

    def observe(self):
        "sets-up model observers"
        super().observe()
        self._histobservers()
        self._widgetobservers()
        self._model.config.observe('eventdetection.isactive', 'binwidth', 'minframes',
                                   lambda: self.reset(False))

class CyclesPlotView(PlotView):
    "Cycles plot view"
    PLOTTER = CyclesPlotCreator
    APPNAME = 'cyclesplot'
    def advanced(self):
        "triggers the advanced dialog"
        self._plotter.advanced()

    def ismain(self):
        "Alignment, ... is set-up by default"
        super()._ismain(tasks  = ['extremumalignment', 'eventdetection'],
                        ioopen = [slice(None, -2),
                                  'control.taskio.ConfigGrFilesIO',
                                  'control.taskio.ConfigTrackIO'])
