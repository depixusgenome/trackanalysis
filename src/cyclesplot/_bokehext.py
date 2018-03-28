#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Cycles plot view"
from typing            import Any

import  bokeh.core.properties as props
from    bokeh.model    import Model
from    bokeh.models   import ColumnDataSource, GlyphRenderer, CustomJS, TapTool

from    sequences.view import SequenceHoverMixin
from    view.plots     import PlotAttrs, DpxHoverTool

class DpxHoverModel(Model, SequenceHoverMixin):  # pylint: disable=too-many-instance-attributes
    "controls keypress actions"
    shape     = props.Tuple(props.Int, props.Int, default = (0, 0))
    cycle     = props.Int(-1)
    framerate = props.Float(1.)
    bias      = props.Float(0.)
    stretch   = props.Float(0.)
    updating  = props.String('')

    impl      = SequenceHoverMixin.impl
    __implementation__ = impl('DpxHoverModel',
                              ('shape: [p.Array, [2,1]],'
                               'cycle: [p.Int, -1],'),
                              __file__)

    def __init__(self, **kwa):
        super().__init__(**kwa) # type: ignore
        SequenceHoverMixin.__init__(self)
        self._rawsource: ColumnDataSource = None
        self._rawglyph:  GlyphRenderer    = None
        self._model:     Any              = None

    @staticmethod
    def defaultconfig(mdl):
        "default config"
        css = mdl.css.raw
        css.defaults = {'selection.dark'  : PlotAttrs('lightblue', 'line',   3),
                        'selection.basic' : PlotAttrs('blue', 'line',   3),
                        'tooltips'        : [(u'(cycle, t, z)',
                                              '(@cycle, $~x{1}, $data_y{1.1111})')],
                        'tooltips.radius' : 1.}
        SequenceHoverMixin.defaultconfig(mdl)

    @staticmethod
    def _createrawdata(data, shape):
        return dict(t = data['t'][:shape[1]], z = data['z'][:shape[1]])

    def createraw(self, fig, source, shape, model):
        "creates the hover tool"
        self._model = model
        self.shape  = tuple(shape)

        css      = self._model.css.raw
        tooltips = css.tooltips.get()
        hover    = fig.select(DpxHoverTool)

        if tooltips is None or len(tooltips) == 0:
            if len(hover):
                hover[0].tooltips = None
        elif len(hover):
            hover[0].tooltips  = tooltips
            hover[0].renderers = [fig.renderers[-1]]
            fig.renderers[-1].selection_glyph        = None
            fig.renderers[-1].nonselection_glyph     = None
            fig.renderers[-1].glyph.radius_dimension = 'x'
            fig.renderers[-1].glyph.radius           = css.tooltips.radius.get()

        tap  = fig.select(TapTool)
        if tap is not None and len(tap):
            self._rawsource = ColumnDataSource(self._createrawdata(source.data, shape))
            sel             = css.selection[self._model.themename].get()
            self._rawglyph  = sel.addto(fig,  x = 't', y = 'z', source = self._rawsource)
            args = dict(hvr    = self,
                        hvrsrc = self._rawsource,
                        rawsrc = source,
                        glyph  = self._rawglyph)
            code = "hvr.launch_hover(rawsrc, hvrsrc, glyph)"
            source.callback = CustomJS(code = code, args = args)

    def createhist(self, fig, mdl, cnf):
        "Creates the hover tool for histograms"
        self.create(fig, mdl, cnf, 'cycles')

    def slaveaxes(self, fig, src):
        "slaves a histogram's axes to its y-axis"
        fig.y_range.callback = CustomJS(code = "hvr.on_change_hist_bounds(fig, src)",
                                        args = dict(hvr = self, fig = fig, src = src))

    def resetraw(self, fig, rdata, shape, resets):
        "updates the tooltips for a new file"
        hover = fig.select(DpxHoverTool)
        if len(hover) == 0:
            return

        resets[self]['shape']             = shape
        if self._rawsource is not None:
            resets[self._rawglyph]['visible'] = False
            resets[self._rawsource]['data']   = self._createrawdata(rdata, shape)

    def resethist(self, resets):
        "updates the tooltips for a new file"
        self.reset(resets)
