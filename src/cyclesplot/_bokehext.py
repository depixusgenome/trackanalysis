#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Cycles plot view"
from typing         import Optional, Tuple      # pylint: disable=unused-import

import  bokeh.core.properties as props
from    bokeh.model    import Model
from    bokeh.models   import (LinearAxis,      # pylint: disable=unused-import
                               ColumnDataSource, GlyphRenderer, Range1d,
                               CustomJS, ContinuousTicker, BasicTicker, Ticker)

from    view.plots.sequence import SequenceHoverMixin, Model
from    view.plots          import PlotAttrs, DpxHoverTool

window = None # type: ignore # pylint: disable=invalid-name
class DpxHoverModel(Model, SequenceHoverMixin):  # pylint: disable=too-many-instance-attributes
    "controls keypress actions"
    framerate = props.Float(1.)
    bias      = props.Float(0.)
    stretch   = props.Float(0.)
    shape     = props.Tuple(props.Int, props.Int, default = (0, 0))
    cycle     = props.Int(0)
    updating  = props.String('')
    __implementation__ = SequenceHoverMixin.impl('DpxHoverModel',
                                                 """
                                                 shape    : [p.Array,  [0, 0]],
                                                 cycle    : [p.Int,  0],
                                                 updating : [p.String, ''],
                                                 """)
    def __init__(self, **kwa):
        super().__init__(**kwa)
        self._rawsource  = ColumnDataSource()
        self._rawglyph   = None # type: Optional[GlyphRenderer]

    @staticmethod
    def defaultconfig() -> dict:
        "default config"
        return {'raw.selection'       : PlotAttrs('green', 'line',   2),
                'raw.tooltips'        : [(u'(cycle, t, z)',
                                          '(@cycle, $~x{1}, $data_y{1.1111})')],
                'raw.tooltips.radius' : 1.5,
                **SequenceHoverMixin.defaultconfig()
               }

    def _createrawdata(self, source):
        return dict(t = source.data['t'][:self.shape[1]],
                    z = source.data['z'][:self.shape[1]])

    def createraw(self, fig, source, shape, css): # pylint: disable = too-many-arguments
        "creates the hover tool"
        self.shape     = tuple(shape)

        hover          = fig.select(DpxHoverTool)
        if len(hover) == 0:
            return

        self._rawsource = ColumnDataSource(self._createrawdata(source))
        attrs           = css.raw.selection.get()
        self._rawglyph  = attrs.addto(fig,  x = 't', y = 'z',
                                      source  = self._rawsource,
                                      visible = False)

        def _onhover(source  = self._rawsource,
                     hvrsrc  = source,
                     glyph   = self._rawglyph,
                     mdl     = self,
                     cb_data = None):
            if mdl.shape == (1, 2):
                return

            if not cb_data.index['1d'].indices.length:
                if glyph.glyph.visible:
                    glyph.glyph.visible = False
                    glyph.trigger('change')
                return

            yval = cb_data['geometry'].y
            best = cb_data.index['1d'].indices[0]
            dist = window.Math.abs(hvrsrc.data['z'][best] - yval)
            for ind in cb_data.index['1d'].indices[1:]:
                tmp = window.Math.abs(hvrsrc.data['z'][ind] - yval)
                if tmp < dist:
                    dist = tmp
                    best = ind

            ind                 = best//mdl.shape[1]
            if ind == mdl.cycle:
                return

            mdl.cycle           = ind
            ind                *= mdl.shape[1]
            source.data['z']    = hvrsrc.data['z'][ind:ind+mdl.shape[1]]
            glyph.glyph.visible = True
            source.trigger('change')

        hover[0].callback = CustomJS.from_py_func(_onhover)
        hover[0].tooltips = None

        tooltips  = css.raw.tooltips.get()
        if tooltips is None or len(tooltips) == 0:
            return

        hover[0].tooltips  = tooltips
        hover[0].renderers = [fig.circle(x                = 't',
                                         y                = 'z',
                                         source           = source,
                                         radius           = css.raw.tooltips.radius.get(),
                                         radius_dimension = 'x',
                                         line_alpha       = 0.,
                                         fill_alpha       = 0.,
                                         visible          = False)]

    def createhist(self, fig, mdl, cnf):
        "Creates the hover tool for histograms"
        source = SequenceHoverMixin.create(self, fig, mdl, cnf.css.hist, cnf.config)
        def _js_cb(source = source, fig = fig, cb_obj = None):
            if cb_obj.updating == '':
                return

            values = cb_obj.bias, cb_obj.stretch
            window.setTimeout(lambda a, b, c: a.setsource(b, c), 500, cb_obj, source, values)
            bases       = fig.extra_y_ranges['bases']
            yrng        = fig.y_range
            bases.start = (yrng.start-cb_obj.bias)/cb_obj.stretch
            bases.end   = (yrng.end  -cb_obj.bias)/cb_obj.stretch

        self.js_on_change("updating", CustomJS.from_py_func(_js_cb))
        cnf.configroot.observe('oligos', self.resetsource)

    def resetraw(self, fig, rdata, shape):
        "updates the tooltips for a new file"
        hover = fig.select(DpxHoverTool)
        if len(hover) == 0:
            return

        self.shape                   = shape
        self._rawsource.data         = self._createrawdata(rdata)
        self._rawglyph.glyph.visible = False

    def resethist(self, hdata):
        "updates the tooltips for a new file"
        mdl  = self.model
        bias = mdl.bias
        if bias is None:
            ind1 = next((i for i,j in enumerate(hdata['cycles']) if j > 0), 0)
            ind2 = next((i for i,j in enumerate(hdata['cycles'][ind1+1:]) if j == 0), ind1+1)
            bias = hdata['bottom'][(ind1+ind2-1)//2] + mdl.binwidth*.5
        SequenceHoverMixin.reset(self, bias = bias)
