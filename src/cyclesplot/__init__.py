#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Cycles plot"
from    typing              import Optional, TYPE_CHECKING # pylint: disable=unused-import

from    bokeh               import layouts
from    bokeh.models        import ToolbarBox

from    control             import Controller
from    control.taskio      import ConfigTrackIO, ConfigGrFilesIO

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
        self.css       .defaults = {'toolbar_location': 'right',
                                    **DpxHoverModel.defaultconfig()
                                   }
        self.config    .defaults = {'tools'      : 'ypan,ybox_zoom,reset,save,dpxhover',
                                    'oligos.size': 4
                                   }
        self.configroot.defaults = {'oligos'                  : [],
                                    'oligos.history'          : [],
                                    'oligos.history.maxlength': 10
                                   }
        self._hover  = None # type: Optional[DpxHoverModel]
        if TYPE_CHECKING:
            self._model = CyclesModelAccess('', '')

    def _figargs(self, css):
        args = super()._figargs(css)
        args['x_axis_label']     = css.xlabel.get()
        if css.plotwidth.get(default = None) is not None:
            args['plot_width']       = css.plotwidth.get()
        if css.plotheight.get(default = None) is not None:
            args['plot_height']      = self.css.plotheight.get()
        args['toolbar_location'] = 'right'
        return args

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

    def _reset(self, items):
        shape = self._resetraw()
        self._resethist(self._rawsource.data, shape)
        self._resetconfig()

class CyclesPlotView(PlotView):
    "Cycles plot view"
    PLOTTER = CyclesPlotCreator
    APPNAME = 'Track Cycles'

    def ismain(self):
        "Alignment, ... is set-up by default"
        tasks         = self._ctrl.getGlobal('config').tasks
        tasks.default = ['alignment']
        ConfigTrackIO.setup(self._ctrl, tasks)

        trk = self._ctrl.getGlobal('current').track
        trk.observe(lambda itm: self._ctrl.clearData(itm.old))
