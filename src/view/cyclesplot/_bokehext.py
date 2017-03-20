#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Cycles plot view"
from typing         import Optional, Tuple      # pylint: disable=unused-import

import  bokeh.core.properties as props
from    bokeh.model    import Model
from    bokeh.models   import (LinearAxis,      # pylint: disable=unused-import
                               ColumnDataSource, GlyphRenderer, Range1d,
                               CustomJS, ContinuousTicker, BasicTicker, Ticker)

import  numpy        as np

import  sequences
from  ..plotutils    import PlotAttrs, checksizes, readsequence, DpxHoverTool

window = None # type: ignore # pylint: disable=invalid-name
class DpxHoverModel(Model):
    "controls keypress actions"
    framerate = props.Float(1.)
    bias      = props.Float(0.)
    stretch   = props.Float(0.)
    shape     = props.Tuple(props.Int, props.Int, default = (0, 0))
    cycle     = props.Int(0)
    updating  = props.Int(0)
    __implementation__ = """
    import * as p  from "core/properties"
    import {Model} from "model"

    export class DpxHoverModelView
    export class DpxHoverModel extends Model
        default_view: DpxHoverModelView
        type:"DpxHoverModel"
        @define {
            framerate : [p.Number, 1],
            stretch   : [p.Number, 0],
            bias      : [p.Number, 0],
            shape     : [p.Array,  [0, 0]],
            cycle     : [p.Int,  0]
            updating  : [p.Int,  0]
        }
    """
    def __init__(self, **kwa):
        super().__init__(**kwa)
        self._rawsource  = ColumnDataSource()
        self._histsource = ColumnDataSource()
        self._rawglyph   = None # type: Optional[GlyphRenderer]

    def source(self, key):
        u"returns the hist source"
        return getattr(self, '_'+key+'source')

    @staticmethod
    def defaultconfig() -> dict:
        "default config"
        return {'raw.selection'       : PlotAttrs('green', 'line',   2),
                'raw.tooltips'        : [(u'(cycle, t, z)',
                                          '(@cycle, $~x{1}, $data_y{1.1111})')],
                'raw.tooltips.radius' : 1.5,
                'hist.tooltips.radius': 1.,
                'hist.tooltips'       : u'@z{1.1111} ↔ @values: @text'
               }

    def _createrawdata(self, source):
        return dict(t = source.data['t'][:self.shape[1]],
                    z = source.data['z'][:self.shape[1]])

    def createraw(self, fig, source, shape, mdl, css): # pylint: disable = too-many-arguments
        "creates the hover tool"
        self.bias      = mdl.bias
        self.stretch   = mdl.stretch
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

    @staticmethod
    @checksizes
    def _createhistdata(mdl, cnf):
        key   = mdl.sequencekey
        oligs = mdl.oligos
        osiz  = max((len(i) for i in oligs), default = cnf.oligos.size.get())
        dseq  = readsequence(mdl.sequencepath)
        if len(dseq) == 0:
            return dict(values = [0], inds = [0], text = [''], z = [0])

        nbases = max(len(i) for i in dseq.values())
        data   = dict(values = np.arange(osiz, nbases+osiz),
                      inds   = np.full((nbases,), 0.5, dtype = 'f4'))
        for name, seq in dseq.items():
            seq        = sequences.marksequence(seq, oligs)
            data[name] = np.full((nbases,), ' ', dtype = 'U%d' % osiz)
            data[name][:len(seq)-osiz+1] = [seq[i:i+osiz] for i in range(len(seq)-osiz+1)]

        data['text'] = data.get(key, data[next(iter(dseq))])
        data['z']    = data['values']*mdl.stretch+(0. if mdl.bias is None else mdl.bias)
        return data

    def createhist(self, fig, mdl, css, cnf):
        "Creates the hover tool for histograms"
        self.update(framerate = 1./30.,
                    bias      = 0.,
                    stretch   = mdl.stretch)

        hover = fig.select(DpxHoverTool)
        if len(hover) == 0:
            return

        self._histsource = ColumnDataSource(self._createhistdata(mdl, cnf))
        hover[0].tooltips   = css.hist.tooltips.get()
        hover[0].mode       = 'hline'

        hover[0].renderers  = [fig.circle(x                = 'inds',
                                          y                = 'values',
                                          source           = self._histsource,
                                          radius           = css.hist.tooltips.radius.get(),
                                          radius_dimension = 'y',
                                          line_alpha       = 0.,
                                          fill_alpha       = 0.,
                                          x_range_name     = 'cycles',
                                          y_range_name     = 'bases',
                                          visible          = False)]

        source = self._histsource
        def _js_cb(source = source, mdl = self, fig = fig):
            zvals   = source.data['z']
            bvals   = source.data['values']
            stretch = mdl.stretch
            bias    = mdl.bias
            for i in range(len(source.data['z'])):
                zvals[i] = bvals[i]*stretch+bias

            source.trigger('change:data')

            bases       = fig.extra_y_ranges['bases']
            yrng        = fig.y_range
            bases.start = (yrng.start-mdl.bias)/mdl.stretch
            bases.end   = (yrng.end  -mdl.bias)/mdl.stretch

        self.js_on_change("updating", CustomJS.from_py_func(_js_cb))

    def updateraw(self, fig, rdata, shape):
        "updates the tooltips for a new file"
        hover = fig.select(DpxHoverTool)
        if len(hover) == 0:
            return

        self.shape                   = shape
        self._rawsource.data         = self._createrawdata(rdata)
        self._rawglyph.glyph.visible = False

    def updatehist(self, fig, hdata, mdl, cnf):
        "updates the tooltips for a new file"
        hover = fig.select(DpxHoverTool)
        if len(hover) == 0:
            return

        self._histsource.data = self._createhistdata(mdl, cnf)
        bias = mdl.bias
        if bias is None:
            ind1 = next((i for i,j in enumerate(hdata['cycles']) if j > 0), 0)
            ind2 = next((i for i,j in enumerate(hdata['cycles'][ind1+1:]) if j == 0), ind1+1)
            bias = hdata['bottom'][(ind1+ind2-1)//2] + mdl.binwidth*.5

        self.update(framerate = getattr(mdl.track, 'framerate', 1./30.),
                    bias      = bias,
                    stretch   = mdl.stretch)

    def observe(self, evts, cnf, mdl):
        u"sets up model observers"
        obs = lambda: setattr(self._histsource, 'data', self._createhistdata(mdl, cnf))
        evts.observe('oligos', obs)

class DpxFixedTicker(ContinuousTicker):
    "Generate ticks at fixed, explicitly supplied locations."
    major      = props.Dict(props.String, props.Seq(props.Float), default = {'': []})
    minor      = props.Dict(props.String, props.Seq(props.Float), default = {'': []})
    key        = props.String(default = '')
    usedefault = props.Bool(default = True)
    base       = props.Instance(Ticker, default = BasicTicker())

    __implementation__ = """
        import {ContinuousTicker} from "models/tickers/continuous_ticker"
        import *             as p from "core/properties"

        export class DpxFixedTicker extends ContinuousTicker
            type: 'DpxFixedTicker'

            @define {
                major:      [ p.Any, {} ]
                minor:      [ p.Any, {} ]
                key:        [ p.String, '']
                usedefault: [ p.Bool,     true]
                base:       [ p.Instance, null]
            }

            get_ticks_no_defaults: (data_low, data_high, desired_n_ticks) ->
                if @usedefault
                    return @base.get_ticks_no_defaults(data_low, data_high,
                                                       desired_n_ticks)
                return {
                    major: @major[@key]
                    minor: @minor[@key]
                }
    """
    def __init__(self, **kwa):
        super().__init__(**kwa)
        self._defaults = dict() # type: Any
        self._withbase = []     # type: Any
        self._axis     = None   # type: Optional[DpxFixedTicker]

    def getaxis(self):
        u"returns the fixed axis"
        return self._axis

    def create(self, css, fig):
        "Sets the ticks according to the configuration"
        if fig.ygrid[0].minor_grid_line_color is None:
            # bokehjs will never draw minor lines unless the color is
            # is set at startup
            fig.ygrid[0].minor_grid_line_color = 'navy'
            fig.ygrid[0].minor_grid_line_alpha = 0.

        order  = tuple('grid_line_'+i for i in ('color', 'width', 'dash', 'alpha'))
        order += tuple('minor_'+i for i in order)  # type: ignore
        order += 'y_range_name',                   # type: ignore
        self._defaults = {i: getattr(fig.ygrid[0], i) for i in order}

        self._withbase = dict()
        for name in ('color', 'dash', 'width', 'alpha'):
            gridprops = css['grid'+name].get()
            self._withbase['grid_line_'+name]       = gridprops[0]
            self._withbase['minor_grid_line_'+name] = gridprops[1]

        fig.extra_y_ranges        = {"bases": Range1d(start = 0., end = 1.)}
        fig.ygrid[0].ticker       = self
        fig.ygrid[0].y_range_name = 'bases'

        if self._axis is None:
            self._axis = type(self)()

        fig.add_layout(LinearAxis(y_range_name = "bases",
                                  axis_label   = css.hist.ylabel.get(),
                                  ticker       = self._axis),
                       'right')

    def observe(self, cnf, mdl, fig):
        u"sets up model observers"
        cnf.observe(('oligos', 'last.path.fasta'), lambda: self.updatedata(mdl, fig))

    @staticmethod
    def defaultconfig() -> dict:
        "default config"
        return dict(gridcolor = ('lightblue', 'lightgreen'),
                    gridwidth = (2,           2),
                    gridalpha = (1.,          1.),
                    griddash  = ('solid',     'solid'))

    def updatedata(self, mdl, fig):
        "Updates the ticks according to the configuration"
        key                   = mdl.sequencekey if len(mdl.oligos) else None
        self.usedefault       = True
        self._axis.usedefault = True
        if key is not None:
            majors = {}
            minors = {}
            for name, seq in readsequence(mdl.sequencepath).items():
                peaks        = sequences.peaks(seq, mdl.oligos)
                majors[name] = tuple(peaks['position'][peaks['orientation']])
                minors[name] = tuple(peaks['position'][~peaks['orientation']])

            self.update(major = majors, minor = minors, key = key)
            self._axis.update(major = {i: majors[i]+minors[i] for i in majors},
                              minor = dict.fromkeys(majors.keys(), tuple()),
                              key   = key)
            self.usedefault       = False
            self._axis.usedefault = False

        info = self._defaults if self.usedefault else self._withbase
        for name in ('color', 'dash', 'width', 'alpha'):
            setattr(fig.ygrid[0], 'grid_line_'+name, info['grid_line_'+name])
            setattr(fig.ygrid[0], 'minor_grid_line_'+name, info['minor_grid_line_'+name])
