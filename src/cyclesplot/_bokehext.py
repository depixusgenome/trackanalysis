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

    # 1 & 2: dummy variables because js_on_change is bugged
    updating1 = props.String('')
    updating2 = props.String('')
    __implementation__ = SequenceHoverMixin.impl('DpxHoverModel',
                                                 """
                                                 shape    : [p.Array,  [0, 0]],
                                                 cycle    : [p.Int,  0],
                                                 updating1: [p.String, ''],
                                                 updating2: [p.String, '']
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
        css.defaults = {'selection.dark'  : PlotAttrs('lightblue', 'line',   3),
                        'selection.basic' : PlotAttrs('blue', 'line',   3),
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

        sel             = css.selection[self._model.css.theme.get()].get()
        self._rawglyph  = sel.addto(fig,  x = 't', y = 'z', source = self._rawsource)

        def _onhover(source  = self._rawsource, # pylint: disable=too-many-arguments
                     hvrsrc  = source,
                     glyph   = self._rawglyph,
                     mdl     = self,
                     cb_data = None,
                     window  = None):
            if mdl.shape == (1, 2):
                return

            if not cb_data.index['1d'].indices.length:
                if glyph.visible:
                    glyph.visible = False
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
            glyph.visible = True
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

    def slaveaxes(self, fig, src, inpy = None): # pylint: disable=arguments-differ
        "slaves a histogram's axes to its y-axis"
        if inpy is None:
            self.__jsslaveaxes(fig, src)
        else:
            self.__pyslaveaxes(fig, src, inpy)

    def __pyslaveaxes(self, fig, src, inpy):
        "slaves a histogram's axes to its y-axis in py"
        yrng = fig.y_range
        mdl  = self._model
        inpy[fig.extra_y_ranges['bases']].update(start = (yrng.start - mdl.bias)*mdl.stretch,
                                                 end   = (yrng.end   - mdl.bias)*mdl.stretch)

        bottom = src['bottom']
        if len(bottom) < 2:
            ind1 = 1
            ind2 = 0
        else:
            delta = bottom[1]-bottom[0]
            ind1  = min(len(bottom), max(0, int((yrng.start-bottom[0])/delta-1)))
            ind2  = min(len(bottom), max(0, int((yrng.end  -bottom[0])/delta+1)))

        get = lambda name: (0. if ind1 >= ind2 else max(src[name][ind1:ind2])+1)
        inpy[fig.extra_x_ranges['cycles']].update(start = 0., end = get('cycles'))
        inpy[fig.x_range]                 .update(start = 0., end = get('frames'))

    def __jsslaveaxes(self, fig, src):
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

        self.shape             = shape
        resets[self._rawsource]['data']   = self._createrawdata(rdata)
        resets[self._rawglyph]['visible'] = False

    def resethist(self, resets):
        "updates the tooltips for a new file"
        self.reset(resets)
