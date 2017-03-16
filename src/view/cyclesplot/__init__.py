#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Cycles plot"
from    typing       import Optional # pylint: disable=unused-import

from    bokeh        import layouts
from    bokeh.models import ToolbarBox

from    control      import Controller

from ..plotutils           import DpxKeyedRow, TrackPlotCreator, TrackPlotView
from  ._bokehext           import DpxHoverModel
from  ._modelcontroller    import CyclesModelController
from  ._raw                import RawMixin
from  ._hist               import HistMixin
from  ._config             import ConfigMixin

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
                                     'oligos'     : [],
                                     'oligos.size': 4}
        self._hover  = None # type: Optional[DpxHoverModel]

    def _figargs(self, css): # pylint: disable=arguments-differ
        args = super()._figargs()
        args['x_axis_label']     = css.xlabel.get()
        args['plot_width']       = css.plotwidth.get()
        args['toolbar_location'] = 'right'
        return args

    def _create(self, track, bead, doc):
        "returns the figure"
        self._hover = DpxHoverModel()
        shape       = self._createraw(track, bead)
        self._createhist(track, self._rawsource.data, shape, self._raw.y_range)

        plts  = layouts.gridplot([[self._raw, self._hist]],
                                 toolbar_location = self.getCSS().toolbar_location.get())
        keyed = DpxKeyedRow(self, self._raw,
                            children = [plts],
                            toolbar  = next(i for i in plts.children
                                            if isinstance(i, ToolbarBox)))

        doc.add_root(self._hover)
        return layouts.column([keyed, self._createconfig()])

    def _update(self, track, bead, items):
        if 'track' in items:
            self._model.clearcache() # pylint: disable=no-member
        shape = self._updateraw(track, bead)
        self._updatehist(track, self._rawsource.data, shape)
        self._updateconfig()

class CyclesPlotView(TrackPlotView):
    "Cycles plot view"
    PLOTTER = CyclesPlotCreator
