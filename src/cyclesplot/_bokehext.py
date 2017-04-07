#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Cycles plot view"
from typing         import Optional, Tuple      # pylint: disable=unused-import

import  bokeh.core.properties as props
from    bokeh.model    import Model
from    bokeh.models   import (LinearAxis,      # pylint: disable=unused-import
                               ColumnDataSource, GlyphRenderer, Range1d,
                               CustomJS, ContinuousTicker, BasicTicker, Ticker)

from    view.plots.sequence import SequenceHoverMixin
from    view.plots          import PlotAttrs, DpxHoverTool

class DpxHoverModel(Model, SequenceHoverMixin):  # pylint: disable=too-many-instance-attributes
    "controls keypress actions"
    shape     = props.Tuple(props.Int, props.Int, default = (0, 0))
    cycle     = props.Int(0)
    framerate = props.Float(1.)
    bias      = props.Float(0.)
    stretch   = props.Float(0.)
    updating  = props.String('')
    __implementation__ = SequenceHoverMixin.impl('DpxHoverModel',
                                                 """
                                                 shape    : [p.Array,  [0, 0]],
                                                 cycle    : [p.Int,  0],
                                                 """)
    def __init__(self, **kwa):
        super().__init__(**kwa)
        SequenceHoverMixin.__init__(self)
        self._rawsource  = None # type: Optional[ColumnDataSource]
        self._rawglyph   = None # type: Optional[GlyphRenderer]
        self._model      = None # type: Any

    @staticmethod
    def defaultconfig(mdl):
        "default config"
        css = mdl.css.raw
        css.defaults = {'selection'       : PlotAttrs('green', 'line',   2),
                        'tooltips'        : [(u'(cycle, t, z)',
                                              '(@cycle, $~x{1}, $data_y{1.1111})')],
                        'tooltips.radius' : 1.5}
        SequenceHoverMixin.defaultconfig(mdl)

    def _createrawdata(self, source):
        return dict(t = source.data['t'][:self.shape[1]],
                    z = source.data['z'][:self.shape[1]])

    def createraw(self, fig, source, shape, model):
        "creates the hover tool"
        self._model = model
        self.shape  = tuple(shape)

        hover       = fig.select(DpxHoverTool)
        if len(hover) == 0:
            return

        self._rawsource = ColumnDataSource(self._createrawdata(source))
        css             = self._model.css.raw
        self._rawglyph  = css.selection.get().addto(fig,  x = 't', y = 'z',
                                                    source  = self._rawsource,
                                                    visible = False)

        def _onhover(source  = self._rawsource, # pylint: disable=too-many-arguments
                     hvrsrc  = source,
                     glyph   = self._rawglyph,
                     mdl     = self,
                     cb_data = None,
                     window  = None):
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

        tooltips  = css.tooltips.get()
        if tooltips is None or len(tooltips) == 0:
            return

        hover[0].tooltips  = tooltips
        hover[0].renderers = [fig.circle(x                = 't',
                                         y                = 'z',
                                         source           = source,
                                         radius           = css.tooltips.radius.get(),
                                         radius_dimension = 'x',
                                         line_alpha       = 0.,
                                         fill_alpha       = 0.,
                                         visible          = False)]

    def createhist(self, fig, mdl, cnf):
        "Creates the hover tool for histograms"
        self.create(fig, mdl, cnf, 'cycles')
        self._model.observeprop('oligos', 'sequencepath', self.resethist)

    def slaveaxes(self, fig, src, inpy = False): # pylint: disable=arguments-differ
        "slaves a histogram's axes to its y-axis"
        super().slaveaxes(fig, src, 'frames', 'cycles', 'bottom', inpy)

    def resetraw(self, fig, rdata, shape):
        "updates the tooltips for a new file"
        hover = fig.select(DpxHoverTool)
        if len(hover) == 0:
            return

        self.shape                   = shape
        self._rawsource.data         = self._createrawdata(rdata)
        self._rawglyph.glyph.visible = False

    def resethist(self):
        "updates the tooltips for a new file"
        self.reset()
