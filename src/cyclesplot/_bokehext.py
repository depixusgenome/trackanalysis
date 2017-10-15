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
                        'tooltips.radius' : 1.5}
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
            hover[0].renderers = [fig.circle(x                = 't',
                                             y                = 'z',
                                             source           = source,
                                             radius           = css.tooltips.radius.get(),
                                             radius_dimension = 'x',
                                             line_alpha       = 0.,
                                             fill_alpha       = 0.)]

        tap  = fig.select(TapTool)
        if tap is not None and len(tap):
            self._rawsource = ColumnDataSource(self._createrawdata(source.data, shape))
            sel             = css.selection[self._model.css.theme.get()].get()
            self._rawglyph  = sel.addto(fig,  x = 't', y = 'z', source = self._rawsource)
            args = dict(hvr    = self,
                        hvrsrc = self._rawsource,
                        rawsrc = source,
                        glyph  = self._rawglyph)
            code = "hvr.launch_hover(rawsrc, hvrsrc, glyph, cb_obj.selected)"
            source.callback = CustomJS(code = code, args = args)

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
        if self._rawsource is not None:
            resets[self._rawglyph]['visible'] = False
            resets[self._rawsource]['data']   = self._createrawdata(rdata, shape)

    def resethist(self, resets):
        "updates the tooltips for a new file"
        self.reset(resets)
