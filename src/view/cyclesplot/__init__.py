#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Cycles plot"
from    typing           import Optional # pylint: disable=unused-import

from    bokeh            import layouts
from    bokeh.models     import ToolbarBox

from    control          import Controller
from    control.taskio   import ConfigTrackIO, ConfigGrFilesIO

from  ..plotutils        import DpxKeyedRow, TrackPlotCreator, TrackPlotView
from   ._bokehext        import DpxHoverModel
from   ._modelcontroller import CyclesModelController
from   ._raw             import RawMixin
from   ._hist            import HistMixin
from   ._config          import ConfigMixin

class CyclesPlotCreator(TrackPlotCreator, HistMixin, RawMixin, ConfigMixin):
    "Displays cycles and their projection"
    _MODEL = CyclesModelController
    def __init__(self,  ctrl:Controller) -> None:
        "sets up this plotter's info"
        TrackPlotCreator.__init__(self, ctrl)
        RawMixin       .__init__(self)
        HistMixin      .__init__(self)
        ConfigMixin    .__init__(self)
        self.getCSS   ().defaults = {'toolbar_location': 'right',
                                     **DpxHoverModel.defaultconfig()}
        self.getConfig().defaults = {'tools'      : 'ypan,ybox_zoom,reset,save,dpxhover',
                                     'oligos.size': 4}
        self._ctrl.getGlobal("config").defaults = {'oligos': [],
                                                   'oligos.history': [],
                                                   'oligos.history.maxlength': 10
                                                  }
        self._hover  = None # type: Optional[DpxHoverModel]

    def _figargs(self, css):                       # pylint: disable=arguments-differ
        args = super()._figargs()
        args['x_axis_label']     = css.xlabel.get()
        if css.plotwidth.get(default = None) is not None:
            args['plot_width']       = css.plotwidth.get()
        if css.plotheight.get(default = None) is not None:
            args['plot_height']      = self.getCSS().plotheight.get()
        args['toolbar_location'] = 'right'
        return args

    def _create(self, doc, track, cycles, bead):   # pylint: disable=arguments-differ
        "returns the figure"
        self._hover = DpxHoverModel()
        shape       = self._createraw(cycles, bead)
        self._createhist(track, self._rawsource.data, shape, self._raw.y_range)

        plts  = layouts.gridplot([[self._raw, self._hist]],
                                 toolbar_location = self.getCSS().toolbar_location.get())
        keyed = DpxKeyedRow(self, self._raw,
                            children = [plts],
                            toolbar  = next(i for i in plts.children
                                            if isinstance(i, ToolbarBox)))

        doc.add_root(self._hover)
        return layouts.column([keyed, self._createconfig()])

    def _update(self, items, track, cycles, bead): # pylint: disable=arguments-differ
        if 'track' in items:
            self._model.clearcache()               # pylint: disable=no-member
        shape = self._updateraw(cycles, bead)
        self._updatehist(track, self._rawsource.data, shape)
        self._updateconfig()

    def _needsupdate(self, items) -> bool:
        "wether the plots should be updated considering the changes that ocurred"
        if 'parent' in items:
            # pylint: disable=no-member
            return self._model.checktask(items['parent'], items['task'])
        else:
            return super()._needsupdate(items)

    def _gettrack(self):
        return self._model.runbead()               # pylint: disable=no-member

class CyclesPlotView(TrackPlotView):
    "Cycles plot view"
    PLOTTER = CyclesPlotCreator
    APPNAME = 'Track Cycles'

    def ismain(self):
        "Alignment, ... is set-up by default"
        trk           = self._ctrl.getGlobal('current').track

        tasks         = self._ctrl.getGlobal('config').tasks
        tasks.default = ['alignment']

        ConfigTrackIO  .setup(self._ctrl, tasks)
        ConfigGrFilesIO.setup(self._ctrl, trk, tasks)

        trk.observe(lambda itm: self._ctrl.clearData(itm.old))

    def getroots(self, doc):
        "adds items to doc"
        self._ctrl.observe("updatetask", "addtask", "removetask",
                           lambda **items: self._plotter.update(items))
        return super().getroots(doc)
