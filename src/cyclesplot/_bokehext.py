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
    cycle     = props.Int(-1)
    framerate = props.Float(1.)
    bias      = props.Float(0.)
    stretch   = props.Float(0.)
    updating  = props.String('')

    impl      = SequenceHoverMixin.impl
    __implementation__ = impl('DpxHoverModel',
                              'shape: [p.Array,  [2, 1]], cycle: [p.Int,  -1],',
                              '''
                              set_hover: (rawsrc, hvrsrc, glyph, inds, value) ->
                                  if @_hvr_cnt != value
                                      return

                                  inds.sort((a,b) => a - b)
                                  ind = inds[Math.floor(inds.length*0.5)]
                                  ind = Math.floor(ind/@shape[1]) * @shape[1]
                                  if ind == @cycle
                                      return

                                  @cycle           = ind
                                  hvrsrc.data['z'] = rawsrc.data['z'][ind...(ind+@shape[1])]
                                  glyph.visible    = true
                                  hvrsrc.trigger('change')

                              launch_hover: (rawsrc, hvrsrc, glyph, data) ->
                                  if @shape[1] == 2
                                      return

                                  @_hvr_cnt = if @_hvr_cnt? then @_hvr_cnt + 1 else 0
                                  inds      = data.index['1d'].indices
                                  if (not inds?) || inds.length == 0
                                      if glyph.visible
                                          glyph.visible = false
                                          glyph.trigger('change')
                                      return

                                  window.setTimeout(((a,b,c,d,e) => @set_hover(a,b,c,d,e)),
                                                    100, rawsrc, hvrsrc, glyph,
                                                    inds, @_hvr_cnt)
                              ''')
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
        css.defaults = {'selection.dark'  : PlotAttrs('lightblue', 'line',   3),
                        'selection.basic' : PlotAttrs('blue', 'line',   3),
                        'tooltips'        : [(u'(cycle, t, z)',
                                              '(@cycle, $~x{1}, $data_y{1.1111})')],
                        'tooltips.radius' : 1.5}
        SequenceHoverMixin.defaultconfig(mdl)

    @staticmethod
    def _createrawdata(data, shape):
        return dict(t = data['t'][:shape[1]], z = data['z'][:shape[1]])

    def createraw(self, fig, source, shape, model):
        "creates the hover tool"
        self._model = model
        self.shape  = tuple(shape)

        hover       = fig.select(DpxHoverTool)
        if len(hover) == 0:
            return

        self._rawsource = ColumnDataSource(self._createrawdata(source.data, shape))
        css             = self._model.css.raw

        sel             = css.selection[self._model.css.theme.get()].get()
        self._rawglyph  = sel.addto(fig,  x = 't', y = 'z', source = self._rawsource)

        args = dict(hvr    = self,
                    hvrsrc = self._rawsource,
                    rawsrc = source,
                    glyph  = self._rawglyph)
        code = "hvr.launch_hover(rawsrc, hvrsrc, glyph, cb_data)"
        hover[0].callback = CustomJS(code = code, args = args)
        hover[0].tooltips = None

        tooltips = css.tooltips.get()
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

    def slaveaxes(self, fig, src):
        "slaves a histogram's axes to its y-axis"
        # pylint: disable=too-many-arguments,protected-access
        hvr = self
        def _onchangebounds(fig = fig, hvr = hvr, src = src):
            yrng = fig.y_range
            if hasattr(yrng, '_initial_start') and yrng.bounds is not None:
                yrng._initial_start = yrng.bounds[0]
                yrng._initial_end   = yrng.bounds[1]

            if not hasattr(fig, 'extra_x_ranges'):
                return

            cycles = fig.extra_x_ranges['cycles']
            frames = fig.x_range

            cycles.start = 0.
            frames.start = 0.

            bases        = fig.extra_y_ranges['bases']
            bases.start  = (yrng.start - hvr.bias)*hvr.stretch
            bases.end    = (yrng.end   - hvr.bias)*hvr.stretch

            bottom       = src.data['bottom']
            if len(bottom) < 2:
                ind1 = 1
                ind2 = 0
            else:
                delta = bottom[1]-bottom[0]
                ind1  = min(len(bottom), max(0, int((yrng.start-bottom[0])/delta-1)))
                ind2  = min(len(bottom), max(0, int((yrng.end  -bottom[0])/delta+1)))

            if ind1 >= ind2:
                cycles.end = 0
                frames.end = 0
            else:
                frames.end = max(src.data['frames'][ind1:ind2])+1
                cycles.end = max(src.data['cycles'][ind1:ind2])+1
        fig.y_range.callback = CustomJS.from_py_func(_onchangebounds)

    def resetraw(self, fig, rdata, shape, resets):
        "updates the tooltips for a new file"
        hover = fig.select(DpxHoverTool)
        if len(hover) == 0:
            return

        resets[self]['shape']             = shape
        resets[self._rawsource]['data']   = self._createrawdata(rdata, shape)
        resets[self._rawglyph]['visible'] = False

    def resethist(self, resets):
        "updates the tooltips for a new file"
        self.reset(resets)
