#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Cycles plot"
from    typing              import Optional, TYPE_CHECKING # pylint: disable=unused-import

from    bokeh               import layouts
from    bokeh.models        import ToolbarBox

from    control             import Controller
from    control.taskio      import ConfigTrackIO, GrFilesIO

from    view.plots          import DpxKeyedRow, PlotView
from    view.plots.tasks    import TaskPlotCreator

from   ._bokehext           import DpxHoverModel
from   ._model              import CyclesModelAccess
from   ._raw                import RawMixin
from   ._hist               import HistMixin
from   ._config             import ConfigMixin

class CyclesPlotCreator(TaskPlotCreator, HistMixin, RawMixin, ConfigMixin):
    "Displays cycles and their projection"
    _MODEL = CyclesModelAccess
    def __init__(self, ctrl:Controller) -> None:
        "sets up this plotter's info"
        TaskPlotCreator.__init__(self, ctrl)
        RawMixin       .__init__(self)
        HistMixin      .__init__(self)
        ConfigMixin    .__init__(self)

        DpxHoverModel.defaultconfig(self)
        self.config    .defaults = {'tools': 'ypan,ybox_zoom,reset,save,dpxhover'}
        self._hover  = None # type: Optional[DpxHoverModel]
        if TYPE_CHECKING:
            self._model = CyclesModelAccess('', '')

    def _create(self, doc):
        "returns the figure"
        self._hover = DpxHoverModel()
        doc.add_root(self._hover)

        shape       = self._createraw()
        self._createhist(self._rawsource.data, shape, self._raw.y_range)

        plts  = layouts.gridplot([[self._raw, self._hist]],
                                 toolbar_location = self.css.toolbar_location.get())
        keyed = DpxKeyedRow(self, self._raw,
                            children = [plts],
                            toolbar  = next(i for i in plts.children
                                            if isinstance(i, ToolbarBox)))

        return layouts.column([keyed, self._createconfig()])

    def _reset(self):
        shape = self._resetraw()
        self._resethist(self._rawsource.data, shape)
        self._resetconfig()

    def observe(self):
        "sets-up model observers"
        super().observe()
        self._histobservers()
        self._configobservers()

class CyclesPlotView(PlotView):
    "Cycles plot view"
    PLOTTER = CyclesPlotCreator
    APPNAME = 'Track Cycles'

    def ismain(self):
        "Alignment, ... is set-up by default"
        tasks         = self._ctrl.getGlobal('config').tasks
        tasks.default = ['extremumalignment']
        tasks.io.open.default = (tuple(tasks.io.open.get()[:-1])
                                 + ('control.taskio.ConfigTrackIO',))
