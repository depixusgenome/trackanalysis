#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Cycles plot view"

from typing         import (Optional,           # pylint: disable=unused-import
                            Sequence, Tuple, cast, TYPE_CHECKING)
from itertools      import product
import re

import  bokeh.core.properties as props
from    bokeh          import layouts
from    bokeh.model    import Model
from    bokeh.plotting import figure, Figure    # pylint: disable=unused-import
from    bokeh.models   import (LinearAxis,      # pylint: disable=unused-import
                               ColumnDataSource, Slider, GlyphRenderer,
                               CustomJS, Range1d, ContinuousTicker, Paragraph,
                               BasicTicker, Ticker, Dropdown, TextInput,
                               DataTable, TableColumn, IntEditor, NumberEditor)

import numpy        as np
from   numpy.lib.index_tricks import as_strided

import sequences
from   utils        import NoArgs
from   control      import Controller
from  .dialog       import FileDialog
from  .plotutils    import (PlotAttrs, DpxKeyedRow, TrackPlotCreator,
                            TrackPlotView, TrackPlotModel, checksizes,
                            readsequence, DpxHoverTool)

window = None # type: ignore # pylint: disable=invalid-name
def configprop(attr):
    "returns a property which links to the config"
    def _getter(self):
        return self.cnf[attr].get()
    def _setter(self, val):
        self.cnf[attr].set(val)
    hmsg  = "link to config's {}".format(attr)
    return property(_getter, _setter, None, hmsg)

def beadorconfig(attr):
    "returns a property which links to the current bead or the config"
    def _getter(self):
        value = self.curr[attr].get().get(self.bead, NoArgs)
        if value is not NoArgs:
            return value
        return self.cnf[attr].get()

    def _setter(self, val):
        cache = self.curr[attr].get()
        if val == self.cnf[attr].get():
            cache.pop(self.bead, None)
        else:
            cache[self.bead] = val
    hmsg  = "link to config's {}".format(attr)
    return property(_getter, _setter, None, hmsg)

class CyclesModel(TrackPlotModel):
    "Model for Cycles View"
    _CACHED = 'base.stretch', 'base.bias', 'sequence.key', 'sequence.witnesses'
    def __init__(self, ctrl, cnf, curr):
        super().__init__(ctrl, cnf, curr)
        cnf.defaults = {'binwidth'          : .003,
                        'minframes'         : 10,
                        'base.bias'         : None,
                        'base.bias.step'    : .0001,
                        'base.bias.ratio'   : .25,
                        'base.stretch'      : 8.8e-4,
                        'base.stretch.start': 5.e-4,
                        'base.stretch.step' : 1.e-5,
                        'base.stretch.end'  : 1.5e-3,
                        'sequence.path' : "../tests/testingcore/hairpins.fasta",
                        'sequence.key'  : 'GF1',
                       }
        cnf.sequence.witnesses.default = None
        for attr in self._CACHED:
            self.curr[attr].setdefault(None)
        self.clearcache()

    def clearcache(self):
        u"updates the model when a new track is loaded"
        self.curr.update({i: dict() for i in self._CACHED})

    binwidth     = cast(float,                   configprop  ('binwidth'))
    minframes    = cast(int,                     configprop  ('minframes'))
    sequencepath = cast(Optional[str],           configprop  ('sequence.path'))
    oligos       = cast(Optional[Sequence[str]], configprop  ('oligos'))
    stretch      = cast(float,                   beadorconfig('base.stretch'))
    bias         = cast(Optional[float],         beadorconfig('base.bias'))
    sequencekey  = cast(Optional[str],           beadorconfig('sequence.key'))
    witnesses    = cast(Optional[Tuple[float,float,float,float]],
                        beadorconfig('sequence.witnesses'))

class DpxHoverModel(Model):
    "controls keypress actions"
    framerate = props.Float(1.)
    bias      = props.Float(0.)
    stretch   = props.Float(0.)
    shape     = props.Tuple(props.Int, props.Int, default = (0, 0))
    cycle     = props.Int(0)
    updating  = props.Bool(False)
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
            updating  : [p.Bool,  false]
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
    def _createhistdata(mdl):
        key   = mdl.sequencekey
        oligs = mdl.oligos
        osiz  = max(len(i) for i in oligs)
        dseq  = readsequence(mdl.sequencepath)
        if len(dseq) == 0:
            return dict(values = [0], inds = [0], text = [''])

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

    def createhist(self, fig, mdl, css):
        "Creates the hover tool for histograms"
        self.update(framerate = 1./30.,
                    bias      = 0.,
                    stretch   = mdl.stretch)

        hover = fig.select(DpxHoverTool)
        if len(hover) == 0:
            return

        self._histsource = ColumnDataSource(self._createhistdata(mdl))
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

    def updateraw(self, fig, rdata, shape):
        "updates the tooltips for a new file"
        hover = fig.select(DpxHoverTool)
        if len(hover) == 0:
            return

        self.shape                   = shape
        self._rawsource.data         = self._createrawdata(rdata)
        self._rawglyph.glyph.visible = False

    def updatehist(self, fig, hdata, mdl):
        "updates the tooltips for a new file"
        hover = fig.select(DpxHoverTool)
        if len(hover) == 0:
            return

        self._histsource.data = self._createhistdata(mdl)
        bias = mdl.bias
        if bias is None:
            ind1 = next((i for i,j in enumerate(hdata['cycles']) if j > 0), 0)
            ind2 = next((i for i,j in enumerate(hdata['cycles'][ind1+1:]) if j == 0), ind1+1)
            bias = hdata['bottom'][(ind1+ind2-1)//2] + mdl.binwidth*.5
        self.update(framerate = mdl.track.framerate,
                    bias      = bias,
                    stretch   = mdl.stretch)

    def observe(self, ctrl, key, mdl):
        u"sets up model observers"
        def _onconfig(items):
            if 'oligos' in items:
                self._histsource.data = self._createhistdata(mdl)

        ctrl.observe(key, _onconfig)

class DpxFixedTicker(ContinuousTicker):
    "Generate ticks at fixed, explicitly supplied locations."

    major   = props.Dict(props.String, props.Seq(props.Float), default = {'': []})
    minor   = props.Dict(props.String, props.Seq(props.Float), default = {'': []})
    key     = props.String(default = '')
    usebase = props.Bool(default = True)
    base    = props.Instance(Ticker, default = BasicTicker())

    _ORDER     = tuple('grid_line_'+i for i in ('color', 'width', 'dash', 'alpha'))
    _ORDER    += tuple('minor_'+i for i in _ORDER) # type: ignore
    _ORDER    += 'y_range_name',                   # type: ignore

    __implementation__ = """
        import {ContinuousTicker} from "models/tickers/continuous_ticker"
        import *             as p from "core/properties"

        export class DpxFixedTicker extends ContinuousTicker
            type: 'DpxFixedTicker'

            @define {
                major:   [ p.Any, {} ]
                minor:   [ p.Any, {} ]
                key:     [ p.String, '']
                usebase: [ p.Bool,     true]
                base:    [ p.Instance, null]
            }

            get_ticks_no_defaults: (data_low, data_high, desired_n_ticks) ->
                if @usebase
                    return @base.get_ticks_no_defaults(data_low, data_high,
                                                       desired_n_ticks)
                return {
                    major: @major[@key]
                    minor: @minor[@key]
                }
    """
    def __init__(self, **kwa):
        super().__init__(**kwa)
        self._defaults = []     # type: list
        self._axis     = None   # type: Optional[DpxFixedTicker]

    def getaxis(self):
        u"returns the fixed axis"
        return self._axis

    def create(self, css, *figs):
        "Sets the ticks according to the configuration"
        self._defaults = []

        for fig in figs:
            if fig.ygrid[0].minor_grid_line_color is not None:
                continue
            # bokehjs will never draw minor lines unless the color is
            # is set at startup
            fig.ygrid[0].minor_grid_line_color = 'navy'
            fig.ygrid[0].minor_grid_line_alpha = 0.

        for fig, name in product(figs, self._ORDER):
            self._defaults.append(getattr(fig.ygrid[0], name))

        for fig in figs:
            fig.extra_y_ranges = {"bases": Range1d(start = 0., end = 1.)}
            fig.ygrid[0].ticker       = self
            fig.ygrid[0].y_range_name = 'bases'

        fig = figs[-1]
        if self._axis is None:
            self._axis = type(self)()

        fig.add_layout(LinearAxis(y_range_name = "bases",
                                  axis_label   = css.hist.ylabel.get(),
                                  ticker       = self._axis),
                       'right')

    def observe(self, ctrl, key, mdl, figs):
        u"sets up model observers"
        def _onconfig(items):
            if 'oligos' in items:
                self.updatedata(mdl, *figs)
        ctrl.observe(key, _onconfig)

    @staticmethod
    def defaultconfig() -> dict:
        "default config"
        return dict(gridcolor = ('lightblue', 'lightgreen'),
                    gridwidth = (2,           2),
                    gridalpha = (1.,          1.),
                    griddash  = ('solid',     'solid'))

    def updatedata(self, mdl, css, *figs):
        "Updates the ticks according to the configuration"
        dseq         = readsequence(mdl.sequencepath)
        self.usebase = len(dseq) == 0
        if self._axis:
            self._axis.usebase = self.usebase
        if self.usebase:
            for (fig, name), val in zip(product(figs, self._ORDER), self._defaults):
                setattr(fig.ygrid[0], name, val)
        else:
            majors = {}
            minors = {}
            axvals = {}
            for name, seq in dseq.items():
                peaks = sequences.peaks(seq, mdl.oligos)
                majors[name] = tuple(peaks['position'][peaks['orientation']])
                minors[name] = tuple(peaks['position'][~peaks['orientation']])
                axvals[name] = majors[name]+minors[name]

            name = mdl.sequencekey
            if name not in dseq:
                name = next(iter(dseq))

            self.update(major = majors, minor = minors, key = name)
            if self._axis:
                self._axis.update(major = axvals,
                                  minor = dict.fromkeys(axvals.keys(), tuple()),
                                  key   = name)

            for fig in figs:
                grd = fig.ygrid[0]
                grd.y_range_name = 'bases'
                for name in ('color', 'dash', 'width', 'alpha'):
                    gridprops = css['grid'+name].get()
                    setattr(grd, 'grid_line_'+name,       gridprops[0])
                    setattr(grd, 'minor_grid_line_'+name, gridprops[1])

class _Mixin:
    if TYPE_CHECKING:
        # pylint: disable=no-self-use,unused-argument
        def getConfig(self):
            "returns the config"
            return

        def getCSS(self):
            "returns the config"
            return

        def key(self, attr:str = '') -> str:
            "returns the plot key"
            return attr

        def _figargs(self, cnf):
            "returns figure args"
            return

class _RawMixin(_Mixin):
    def __init__(self):
        "sets up this plotter's info"
        self.getCSS().defaults = dict(raw = PlotAttrs('color',  'circle', 1,
                                                      alpha   = .5,
                                                      palette = 'inferno'),
                                      plotwidth = 500)
        self._rawsource = None # type: Optional[ColumnDataSource]
        self._raw       = None # type: Optional[Figure]

    def __data(self, track, bead) -> Tuple[dict, Tuple[int,int]]:
        if track is None:
            return (dict.fromkeys(('t', 'z', 'cycle', 'color'), [0., 1.]),
                    (1, 2))

        items = list(track.cycles[bead,...])
        if len(items) == 0 or max(len(i) for _, i in items) == 0:
            return self.__data(None, bead)

        size = max(len(i) for _, i in items)
        val  = np.full((len(items), size), np.NaN, dtype = 'f4')
        for i, (_, j) in zip(val, items):
            i[:len(j)] = j

        tmp   = np.arange(size, dtype = 'i4')
        time  = as_strided(tmp, shape = val.shape, strides = (0, tmp.strides[0]))

        tmp   = np.array([i[-1] for i, _ in items], dtype = 'i4')
        cycle = as_strided(tmp, shape = val.shape, strides = (tmp.strides[0], 0))

        tmp   = np.array(self.getCSS().raw.get().listpalette(val.shape[0]))
        color = as_strided(tmp, shape = val.shape, strides = (tmp.strides[0], 0))

        return (dict(t     = time .ravel(), z     = val  .ravel(),
                     cycle = cycle.ravel(), color = color.ravel()),
                val.shape)

    def _addcallbacks(self):
        fig = self._raw
        super()._addcallbacks(fig)

        def _onchangebounds(frng = fig.x_range,
                            trng = fig.extra_x_ranges["time"],
                            mdl  = self._hover):
            # pylint: disable=protected-access,no-member
            if frng.bounds is not None:
                frng._initial_start = frng.bounds[0]
                frng._initial_end   = frng.bounds[1]
            trng.start = frng.start/mdl.framerate
            trng.end   = frng.end  /mdl.framerate
        fig.x_range.callback = CustomJS.from_py_func(_onchangebounds)

    def _createraw(self, track, bead):
        css             = self.getCSS()
        self._raw       = figure(y_axis_label = css.ylabel.get(),
                                 y_range      = Range1d(start = 0., end = 1.),
                                 **self._figargs(css))
        raw, shape      = self.__data(track, bead)
        self._rawsource = ColumnDataSource(data = raw)

        css.raw.addto(self._raw, x = 't', y = 'z', source = self._rawsource)

        self._hover.createraw(self._raw, self._rawsource, shape,
                              self._model, self.getCSS())
        self._raw.extra_x_ranges = {"time": Range1d(start = 0., end = 1.)}

        axis = LinearAxis(x_range_name="time", axis_label = css.xtoplabel.get())
        self._raw.add_layout(axis, 'above')
        return shape

    def _updateraw(self, track, bead):
        self._raw.disabled          = False
        self._rawsource.data, shape = self.__data(track, bead)
        self._hover.updateraw(self._raw, self._rawsource, shape)
        return shape

class _HistMixin(_Mixin):
    __PHASE = 5
    def __init__(self):
        "sets up this plotter's info"
        css = self.getCSS()
        css.defaults = {'frames'    : PlotAttrs('white', 'quad',   1,
                                                line_color = 'gray',
                                                fill_color = 'gray'),
                        'cycles'    : PlotAttrs('white', 'quad',   1,
                                                fill_color = None,
                                                line_alpha = .5,
                                                line_color = 'blue'),
                        **DpxFixedTicker.defaultconfig()
                       }
        css.hist.defaults = dict(xtoplabel = u'Cycles',
                                 xlabel    = u'Frames',
                                 ylabel    = u'Base number',
                                 plotwidth = 200)

        self._histsource = None # type: Optional[ColumnDataSource]
        self._hist       = None # type: Optional[Figure]
        self._gridticker = None # type: Optional[DpxFixedTicker]

    @checksizes
    def __data(self, track, data, shape):
        if shape == (1, 2):
            bins  = np.array([-1, 1])
            zeros = np.zeros((1,), dtype = 'f4')
            items = zeros,
        else:
            zvals = data['z'].reshape(shape)
            ind1  = track.phases[:,self.__PHASE]  -track.phases[:,0]
            ind2  = track.phases[:,self.__PHASE+1]-track.phases[:,0]
            items = [val[ix1:ix2] for ix1, ix2, val in zip(ind1, ind2, zvals)]

            rng   = (np.nanmin([np.nanmin(i) for i in items]),
                     np.nanmax([np.nanmax(i) for i in items]))

            width = self._model.binwidth
            bins  = np.arange(rng[0]-width*.5, rng[1]+width*1.01, width, dtype = 'f4')
            if bins[-2] > rng[1]:
                bins = bins[:-1]

            items = [np.bincount(np.digitize(i, bins), minlength = len(bins))[1:]
                     for i in items]
            zeros = np.zeros((len(bins)-1,), dtype = 'f4')

        threshold = self._model.minframes
        return dict(frames  = np.sum(items, axis = 0),
                    cycles  = np.sum([np.int32(i > threshold) for i in items], axis = 0),
                    left    = zeros,
                    bottom  = bins[:-1],
                    top     = bins[1:])

    def _slavexaxis(self):
        # pylint: disable=protected-access,no-member
        def _onchangebounds(hist = self._hist, mdl = self._hover, src= self._histsource):
            yrng = hist.y_range
            if yrng.bounds is not None:
                yrng._initial_start = yrng.bounds[0]
                yrng._initial_end   = yrng.bounds[1]

            cycles       = hist.extra_x_ranges["cycles"]
            frames       = hist.x_range

            cycles.start = 0.
            frames.start = 0.

            bases        = hist.extra_y_ranges['bases']
            bases.start  = (yrng.start-mdl.bias)/mdl.stretch
            bases.end    = (yrng.end-mdl.bias)/mdl.stretch

            bottom = src.data["bottom"]
            delta  = bottom[1]-bottom[0]

            ind1   = min(len(bottom), max(0, int((yrng.start-bottom[0])/delta-1)))
            ind2   = min(len(bottom), max(0, int((yrng.end  -bottom[0])/delta+1)))

            if ind1 >= ind2:
                return

            frames.end = window.Math.max.apply(None, src.data['frames'][ind1:ind2])+1
            cycles.end = window.Math.max.apply(None, src.data['cycles'][ind1:ind2])+1

        self._hist.y_range.callback = CustomJS.from_py_func(_onchangebounds)

    def _createhist(self, track, data, shape, yrng):
        css              = self.getCSS()
        self._hist       = figure(y_axis_location = None,
                                  y_range         = yrng,
                                  **self._figargs(css.hist))

        hist             = self.__data(track, data, shape)
        self._histsource = ColumnDataSource(data = hist)
        self._hist.extra_x_ranges = {"cycles": Range1d(start = 0., end = 1.)}

        attrs = css.cycles.get()
        axis  = LinearAxis(x_range_name          = "cycles",
                           axis_label            = css.hist.xtoplabel.get(),
                           axis_label_text_color = attrs.line_color
                          )
        self._hist.add_layout(axis, 'above')

        css.frames.addto(self._hist,
                         source = self._histsource,
                         bottom = "bottom", top   = "top",
                         left   = "left",   right = "frames")

        attrs.addto(self._hist,
                    source = self._histsource,
                    bottom = "bottom", top   = "top",
                    left   = "left",   right = "cycles",
                    x_range_name = "cycles")

        self._gridticker = DpxFixedTicker()
        self._gridticker.create(self.getCSS(), self._hist)
        self._gridticker.observe(self._ctrl, self.key(), self._model, self._hist)

        self._hover.createhist(self._hist, self._model, self.getCSS())
        self._hover.observe(self._ctrl, self.key(), self._model)
        self._slavexaxis()

    def _updatehist(self, track, data, shape):
        self._hist.disabled   = False
        self._histsource.data = hist = self.__data(track, data, shape)
        self._hover.updatehist(self._hist, hist, self._model)
        self.setbounds(self._hist.y_range, 'y', (hist['bottom'][0], hist['top'][-1]))
        self._gridticker.updatedata(self._model, self.getCSS(), self._hist)

class _ConfigMixin(_Mixin):
    def __init__(self):
        self.__updates = []   # type: List[Callable]
        self.getCSS().defaults = {'tablesize'      : (200, 100),
                                  'title.table'    : u'[nm] ↔ [base] in positions',
                                  'title.sequence' : u'Selected DNA sequence',
                                  'title.stretch'  : u'[nm] ↔ [base] stretch',
                                  'title.bias'     : u'[nm] ↔ [base] bias'}

    def _createconfig(self):
        stretch, bias  = self.__doconvert()
        par,     table = self.__dowitness()
        ret = layouts.layout([[layouts.widgetbox([bias, stretch]),
                               layouts.widgetbox([par,  table])],
                              [layouts.widgetbox(list(self.__dosequence())),
                               self.__dooligos ()]])

        def _py_cb(attr, old, new):
            setattr(self._model, attr, new)

        for name in 'stretch', 'bias':
            self._hover.on_change(name, _py_cb)

        # pylint: disable=too-many-arguments,protected-access,consider-using-enumerate
        # do this here because the trigger on _hover attributes doesn't work
        def _js_cb(stretch = stretch,
                   bias    = bias,
                   data    = table.source,
                   fig     = self._hist,
                   mdl     = self._hover,
                   ttsrc   = self._hover._histsource):
            # pylint: disable=no-member
            if mdl.updating:
                return
            aval = stretch.value
            bval = bias.value

            mdl.updating   = True
            data.data['z'] = [data.data['bases'][0]*aval+bval,
                              data.data['bases'][1]*aval+bval]

            mdl.stretch    = aval
            mdl.bias       = bval

            fig.extra_y_ranges['bases'].start = (fig.y_range.start-bval)/aval
            fig.extra_y_ranges['bases'].end   = (fig.y_range.end-bval)/aval

            zvals = ttsrc.data['z']
            bvals = ttsrc.data['values']
            for i in range(len(zvals)):
                zvals[i] = bvals[i]*aval+bval

            data.trigger('change:data')
            ttsrc.trigger('change:data')
            mdl.updating   = False

        cust = CustomJS.from_py_func(_js_cb)
        for widget in (stretch, bias):
            widget.js_on_change('value', cust)

        # do this here because the trigger on _hover attributes doesn't work
        def _jstable_cb(stretch = stretch,
                        bias    = bias,
                        data    = table.source,
                        fig     = self._hist,
                        mdl     = self._hover,
                        ttsrc   = self._hover._histsource):
            # pylint: disable=no-member
            if mdl.updating:
                return

            zval  = data.data['z']
            bases = data.data['bases']
            if zval[0] == zval[1] or bases[0] == bases[1]:
                return

            aval          = (zval[1]-zval[0]) / (bases[1]-bases[0])
            bval          = zval[0] - bases[0]*aval

            mdl.updating  = True
            stretch.value = aval
            bias.value    = bval

            mdl.stretch   = aval
            mdl.bias      = bval

            fig.extra_y_ranges['bases'].start = (fig.y_range.start-bval)/aval
            fig.extra_y_ranges['bases'].end   = (fig.y_range.end-bval)/aval

            zvals = ttsrc.data['z']
            bvals = ttsrc.data['values']
            for i in range(len(zvals)):
                zvals[i] = bvals[i]*aval+bval

            ttsrc.trigger('change:data')
            mdl.updating = False

        # pylint: disable=no-member
        table.source.js_on_change("data", CustomJS.from_py_func(_jstable_cb))
        return ret

    def _updateconfig(self):
        for fcn in self.__updates:
            fcn()

    def __doconvert(self):
        widget = lambda x, s, e: Slider(value = getattr(self._model, x),
                                        title = self.getCSS().title[x].get(),
                                        step  = self.getConfig().base[x].step.get(),
                                        start = s, end = e)

        stretch = widget('stretch', *self.getConfig().base.stretch.get('start', 'end'))
        bias    = widget('bias', -1., 1.)

        def _onupdate():
            stretch.value = self._model.stretch
            minv  = self._histsource.data['bottom'][0]
            delta = self._histsource.data['top'][-1] - minv
            ratio = self.getConfig().base.bias.ratio.get()
            bias.update(value = self._model.bias, start = minv, end = minv+delta*ratio)

        def _onconfig(items):
            if any(i in items  for i in ('base.stretch', 'base.bias')):
                _onupdate()

        self._ctrl.observe(self.key(),          _onconfig)
        self._ctrl.observe(self.key("current"), _onconfig)
        self.__updates.append(_onupdate)
        return stretch, bias

    def __dowitness(self):
        def _createdata():
            info = self._model.witnesses
            if (self._model.sequencekey is not None
                    and len(self._model.oligos)
                    and info is None):
                seq   = readsequence(self._model.sequencepath)[self._model.sequencekey]
                peaks = sequences.peaks(seq, self._model.oligos)['position']
                if len(peaks) > 2:
                    info = (peaks[0], peaks[-1],
                            peaks[0] *self._hover.stretch+self._hover.bias,
                            peaks[-1]*self._hover.stretch+self._hover.bias)
            if info is None:
                info = (0., 1e3, self._hover.bias, self._hover.stretch)
            return dict(bases = info[:2], z = info[2:])

        size = self.getCSS().tablesize.get()
        data = ColumnDataSource(_createdata())
        cols = [TableColumn(field  = 'bases',
                            title  = self.getCSS().hist.ylabel.get(),
                            editor = IntEditor(),
                            width  = size[0]//2),
                TableColumn(field  = 'z',
                            title  = self.getCSS().ylabel.get(),
                            editor = NumberEditor(step = 1e-4),
                            width  = size[0]//2)]

        widget = DataTable(source      = data,
                           columns     = cols,
                           editable    = True,
                           row_headers = False,
                           width       = size[0],
                           height      = size[1])
        def _py_cb(attr, old, new):
            self._model.witnesses = tuple(data.data['bases']) + tuple(data.data['z'])
        data.on_change("data", self.action(_py_cb))

        def _onconfig(items):
            if 'sequence.witnesses' in items:
                data.data = _createdata()

        self._ctrl.observe(self.key("current"), _onconfig)
        self.__updates.append(lambda: setattr(data, 'data', _createdata()))
        return Paragraph(text = self.getCSS().title.table.get()), widget

    def __dosequence(self):
        dia = FileDialog(filetypes = 'fasta|*',
                         config    = self._ctrl,
                         title     = u'Open a fasta file')
        lst = []
        def _attrs(lst = lst): # pylint: disable = dangerous-default-value
            lst.clear()
            lst.extend(sorted(readsequence(self._model.sequencepath).keys()))

            key   = self._model.sequencekey
            val   = key if key in lst else None
            menu  = [(i, i) for i in lst] if len(lst) else [('→', '→')]
            menu += [None, (u'Find path', '←')]
            return dict(menu  = menu,
                        label = lst[-1][0] if val is None else key,
                        value = lst[0][1]  if val is None else val)

        widget = Dropdown(**_attrs())

        def _py_cb(new, lst = lst): #pylint: disable=dangerous-default-value
            if new in lst:
                self._model.sequencekey = new
            else:
                path = dia.open()
                seqs = readsequence(path)
                if len(seqs) > 0:
                    self._model.sequencepath = path
                    self._model.sequencekey  = next(iter(seqs))

        def _js_cb(choice  = widget,
                   ticker   = self._gridticker,
                   axticker = self._gridticker.getaxis(),
                   tsrc     = self._hover.source('hist')):
            if choice.value in tsrc.column_names:
                choice.label      = choice.value
                ticker.key        = choice.value
                axticker.key      = choice.value
                tsrc.data['text'] = tsrc.data[choice.value]
                tsrc.trigger("change")

        widget.on_click(self.action(_py_cb))
        widget.js_on_change('value', CustomJS.from_py_func(_js_cb))
        def _onconfig(items):
            if any(i in items for i in ('sequence.key', 'sequence.path')):
                widget.update(**_attrs())
        self._ctrl.observe(self.key(), _onconfig)
        self.__updates.append(lambda: widget.update(**_attrs()))
        return Paragraph(text = self.getCSS().title.sequence.get()), widget

    def __dooligos(self):
        attrs  = lambda: {'value': ', '.join(sorted(j.lower() for j in self._model.oligos))}
        widget = TextInput(**attrs(), title = u'Oligos')

        match  = re.compile(r'(?:[^atgc]*)([atgc]+)(?:[^atgc]+|$)*',
                            re.IGNORECASE).findall
        def _py_cb(attr, old, new):
            self._model.oligos = sorted({i.lowercase() for i in match(new)})
        widget.on_change('value', self.action(_py_cb))

        def _onconfig(items):
            if 'oligos' in items:
                widget.update(**attrs())
        self._ctrl.observe(self.key(), _onconfig)
        return widget

class CyclesPlotCreator(TrackPlotCreator, _HistMixin, _RawMixin, _ConfigMixin):
    "Displays cycles and their projection"
    _MODEL = CyclesModel
    def __init__(self,  ctrl:Controller) -> None:
        "sets up this plotter's info"
        TrackPlotCreator.__init__(self, ctrl)
        _RawMixin       .__init__(self)
        _HistMixin      .__init__(self)
        _ConfigMixin    .__init__(self)
        self.getCSS   ().defaults = {'toolbar_location': 'right',
                                     **DpxHoverModel.defaultconfig()}
        self.getConfig().defaults = dict(tools   = 'ypan,ybox_zoom,reset,save,dpxhover',
                                         ncycles = 150,
                                         oligos  = ['CTGT'])
        self._hover  = None # type: Optional[DpxHoverModel]

    def _figargs(self, css): # pylint: disable=arguments-differ
        args = super()._figargs()
        args['x_axis_label']     = css.xlabel.get()
        args['plot_width']       = css.plotwidth.get()
        args['toolbar_location'] = 'right'
        return args

    def _create(self, track, bead):
        "returns the figure"
        self._hover = DpxHoverModel()
        shape       = self._createraw(track, bead)
        self._createhist(track, self._rawsource.data, shape, self._raw.y_range)

        plts  = layouts.gridplot([[self._raw, self._hist]],
                                 toolbar_location = self.getCSS().toolbar_location.get())
        keyed = DpxKeyedRow(self, self._raw,
                            children = [plts],
                            toolbar  = plts.children[0])

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
