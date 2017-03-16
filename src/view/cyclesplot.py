#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Cycles plot view"

from typing         import (Optional, List,    # pylint: disable=unused-import
                            Sequence, Tuple, cast, TYPE_CHECKING)
import re

import  bokeh.core.properties as props
from    bokeh          import layouts
from    bokeh.model    import Model
from    bokeh.plotting import figure, Figure    # pylint: disable=unused-import
from    bokeh.models   import (LinearAxis,      # pylint: disable=unused-import
                               ColumnDataSource, Slider, GlyphRenderer,
                               CustomJS, Range1d, ContinuousTicker, Paragraph,
                               BasicTicker, Ticker, Dropdown, TextInput,
                               DataTable, TableColumn, IntEditor, NumberEditor,
                               ToolbarBox)

import numpy        as np
from   numpy.lib.index_tricks import as_strided

import sequences
from   utils        import NoArgs
from   control      import Controller
from  .dialog       import FileDialog
from  .base         import enableOnTrack
from  .plotutils    import (PlotAttrs, DpxKeyedRow, TrackPlotCreator,
                            TrackPlotView, TrackPlotModelController, checksizes,
                            readsequence, DpxHoverTool, WidgetCreator)

window = None # type: ignore # pylint: disable=invalid-name
def configprop(attr):
    "returns a property which links to the config"
    def _getter(self):
        return self.getConfig()[attr].get()
    def _setter(self, val):
        self.getConfig()[attr].set(val)
    hmsg  = "link to config's {}".format(attr)
    return property(_getter, _setter, None, hmsg)

def beadorconfig(attr):
    "returns a property which links to the current bead or the config"
    def _getter(self):
        value = self.getCurrent()[attr].get().get(self.bead, NoArgs)
        if value is not NoArgs:
            return value
        return self.getConfig()[attr].get()

    def _setter(self, val):
        cache = self.getCurrent()[attr].get()
        if val == self.getConfig()[attr].get():
            cache.pop(self.bead, None)
        else:
            cache[self.bead] = val
    hmsg  = "link to config's {}".format(attr)
    return property(_getter, _setter, None, hmsg)

class CyclesModelController(TrackPlotModelController):
    "Model for Cycles View"
    _CACHED = 'base.stretch', 'base.bias', 'sequence.key', 'sequence.witnesses'
    def __init__(self, ctrl, key):
        super().__init__(ctrl, key)
        self.getConfig().defaults = {'binwidth'          : .003,
                                     'minframes'         : 10,
                                     'base.bias'         : None,
                                     'base.bias.step'    : .0001,
                                     'base.bias.ratio'   : .25,
                                     'base.stretch'      : 8.8e-4,
                                     'base.stretch.start': 5.e-4,
                                     'base.stretch.step' : 1.e-5,
                                     'base.stretch.end'  : 1.5e-3,
                                     'sequence.path' : None,
                                     'sequence.key'  : None,
                                    }
        self.getConfig().sequence.witnesses.default = None
        for attr in self._CACHED:
            self.getCurrent()[attr].setdefault(None)
        self.clearcache()

    def clearcache(self):
        u"updates the model when a new track is loaded"
        self.getCurrent().update({i: dict() for i in self._CACHED})

    binwidth     = cast(float,                   configprop  ('binwidth'))
    minframes    = cast(int,                     configprop  ('minframes'))
    sequencepath = cast(Optional[str],           configprop  ('sequence.path'))
    oligos       = cast(Optional[Sequence[str]], configprop  ('oligos'))
    stretch      = cast(float,                   beadorconfig('base.stretch'))
    bias         = cast(Optional[float],         beadorconfig('base.bias'))
    witnesses    = cast(Optional[Tuple[float,float,float,float]],
                        beadorconfig('sequence.witnesses'))

    _sequencekey = cast(Optional[str],           beadorconfig('sequence.key'))
    @property
    def sequencekey(self) -> Optional[str]:
        "returns the current sequence key"
        key  = self._sequencekey
        dseq = readsequence(self.sequencepath)
        if key not in dseq:
            return next(iter(dseq), None)

    @sequencekey.setter
    def sequencekey(self, value) -> Optional[str]:
        self._sequencekey = value
        return self._sequencekey

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
            for i in range(len(zvals)): # pylint: disable=consider-using-enumerate
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

    def observe(self, cnf, mdl):
        u"sets up model observers"
        obs = lambda: setattr(self._histsource, 'data', self._createhistdata(mdl, cnf))
        cnf.observe('oligos', obs)

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
        cnf.observe('oligos', lambda: self.updatedata(mdl, fig))

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

    def __addcallbacks(self):
        fig = self._raw
        self._addcallbacks(fig)

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
                                 y_range      = Range1d(start = 0., end = 0.),
                                 **self._figargs(css))
        raw, shape      = self.__data(track, bead)
        self._rawsource = ColumnDataSource(data = raw)

        css.raw.addto(self._raw, x = 't', y = 'z', source = self._rawsource)

        self._hover.createraw(self._raw, self._rawsource, shape,
                              self._model, self.getCSS())
        self._raw.extra_x_ranges = {"time": Range1d(start = 0., end = 0.)}

        axis = LinearAxis(x_range_name="time", axis_label = css.xtoplabel.get())
        self._raw.add_layout(axis, 'above')
        self.__addcallbacks()
        return shape

    def _updateraw(self, track, bead):
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
        self._hist.extra_x_ranges = {"cycles": Range1d(start = 0., end = 0.)}

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
        self._gridticker.observe(self.getConfig(), self._model, self._hist)

        self._hover.createhist(self._hist, self._model, self.getCSS(), self.getConfig())
        self._hover.observe(self.getConfig(), self._model)
        self._slavexaxis()

    def _updatehist(self, track, data, shape):
        self._histsource.data = hist = self.__data(track, data, shape)
        self._hover.updatehist(self._hist, hist, self._model, self.getConfig())
        self.setbounds(self._hist.y_range, 'y', (hist['bottom'][0], hist['top'][-1]))
        self._gridticker.updatedata(self._model, self._hist)

class _PeakTableCreator(WidgetCreator):
    "Table creator"
    def __init__(self, ctrl:Controller, model:TrackPlotModelController, key:str) -> None:
        super().__init__(ctrl, model, key)
        self.__widget = None # type: Optional[DataTable]
        self.__hover  = None # type: DpxHoverModel
        self.getCSS().defaults = {'tablesize'   : (200, 100),
                                  'title.table' : u'dna ↔ nm'}

    def create(self, hover):
        "creates the widget"
        size = self.getCSS().tablesize.get()
        cols = [TableColumn(field  = 'bases',
                            title  = self.getCSS().hist.ylabel.get(),
                            editor = IntEditor(),
                            width  = size[0]//2),
                TableColumn(field  = 'z',
                            title  = self.getCSS().ylabel.get(),
                            editor = NumberEditor(step = 1e-4),
                            width  = size[0]//2)]


        self.__hover  = hover
        self.__widget = DataTable(source      = ColumnDataSource(self.__data()),
                                  columns     = cols,
                                  editable    = True,
                                  row_headers = False,
                                  width       = size[0],
                                  height      = size[1])
        return Paragraph(text = self.getCSS().title.table.get()), self.__widget

    def update(self):
        "updates the widget"
        self.__widget.source.data = self.__data()

    def __data(self):
        info = self._model.witnesses
        if (self._model.sequencekey is not None
                and len(self._model.oligos)
                and info is None):
            seq   = readsequence(self._model.sequencepath)[self._model.sequencekey]
            peaks = sequences.peaks(seq, self._model.oligos)['position']
            if len(peaks) > 2:
                info = peaks[0], peaks[-1]

        if info is None:
            info = 0., 1e3

        info += (info[0]*self.__hover.stretch+self.__hover.bias,
                 info[1]*self.__hover.stretch+self.__hover.bias)

        return dict(bases = info[:2], z = info[2:])

    def callbacks(self, action, stretch, bias):
        "adding callbacks"
        source = self.__widget.source
        hover  = self.__hover
        def _py_cb(attr, old, new):
            self._model.witnesses = tuple(source.data['bases'])

            zval  = source.data['z']
            bases = source.data['bases']
            if zval[0] == zval[1] or bases[0] == bases[1]:
                return

            self._model.stretch = (zval[1]-zval[0]) / (bases[1]-bases[0])
            self._model.bias    = zval[0] - bases[0]*self._model.stretch

        source.on_change("data", action(_py_cb)) # pylint: disable=no-member

        self.getCurrent().observe(('oligos', 'sequence.witnesses'),
                                  lambda: setattr(source, 'data', self.__data()))

        # pylint: disable=no-member,function-redefined
        def _js_cb(source = source, mdl = hover, stretch = stretch, bias = bias):
            zval  = source.data['z']
            bases = source.data['bases']
            if zval[0] == zval[1] or bases[0] == bases[1]:
                return

            aval = (zval[1]-zval[0]) / (bases[1]-bases[0])
            bval = zval[0] - bases[0]*aval

            stretch.value = aval
            bias   .value = bval
            mdl.stretch   = aval
            mdl.bias      = bval
            mdl.updating += 1

        source.js_on_change("data", CustomJS.from_py_func(_js_cb))

class _SliderCreator(WidgetCreator):
    "Slider creator"
    def __init__(self, ctrl:Controller, model:TrackPlotModelController, key:str) -> None:
        super().__init__(ctrl, model, key)
        self.__stretch = None # type: Optional[Slider]
        self.__bias    = None # type: Optional[Slider]
        self.__figdata = None # type: Optional[ColumnDataSource]
        self.getCSS().defaults = {'title.stretch'    : u'stretch [dna/nm]',
                                  'title.bias'       : u'bias [nm]'}

    def create(self, figdata):
        "creates the widget"
        widget = lambda x, s, e: Slider(value = getattr(self._model, x),
                                        title = self.getCSS().title[x].get(),
                                        step  = self.getConfig().base[x].step.get(),
                                        start = s, end = e)

        self.__stretch = widget('stretch', *self.getConfig().base.stretch.get('start', 'end'))
        self.__bias    = widget('bias', -1., 1.)
        self.__figdata = figdata
        return self.__stretch, self.__bias

    def update(self):
        "updates the widgets"
        minv  = self.__figdata.data['bottom'][0]
        delta = self.__figdata.data['top'][-1] - minv
        ratio = self.getConfig().base.bias.ratio.get()
        self.__bias.update(value = self._model.bias,
                           start = minv,
                           end   = minv+delta*ratio)
        self.__stretch.value = self._model.stretch

    def callbacks(self, action, hover, table):
        "adding callbacks"
        self.getConfig() .observe(('base.stretch', 'base.bias'), self.update)
        self.getCurrent().observe(('base.stretch', 'base.bias'), self.update)

        stretch, bias = self.__stretch, self.__bias

        # pylint: disable=function-redefined
        def _py_cb(attr, old, new):
            self._model.stretch = new
        stretch.on_change('value', action(_py_cb))

        def _py_cb(attr, old, new):
            self._model.bias = new
        bias   .on_change('value', action(_py_cb))

        source = table.source
        def _js_cb(stretch = stretch, bias = bias, mdl = hover, source = source):
            mdl.stretch  = stretch.value
            mdl.bias     = bias.value
            mdl.updating = mdl.updating+1

            bases            = source.data['bases']
            source.data['z'] = [bases[0] * stretch.value + bias.value,
                                bases[1] * stretch.value + bias.value]
            source.trigger('change:data')

        cust = CustomJS.from_py_func(_js_cb)
        stretch.js_on_change('value', cust)
        bias   .js_on_change('value', cust)

class _SequenceCreator(WidgetCreator):
    "Sequence Droppdown creator"
    def __init__(self, ctrl:Controller, model:TrackPlotModelController, key:str) -> None:
        super().__init__(ctrl, model, key)
        self.__widget  = None # type: Optional[Dropdown]
        self.__list    = []   # type: List[str]
        self.__hover   = None # type: Optional[DpxHoverModel]
        self.__dialog  = None # type: Optional[FileDialog]
        self.getCSS().defaults = {'title.fasta'      : u'Open a fasta file',
                                  'title.sequence'   : u'Selected DNA sequence',
                                  'title.sequence.missing.key' : u'Select sequence',
                                  'title.sequence.missing.path': u'Find path'}

    def create(self, action, hover, tick1, tick2):
        "creates the widget"
        self.__dialog = FileDialog(filetypes = 'fasta|*',
                                   config    = self._ctrl,
                                   title     = self.getCSS().title.fasta.get())

        self.__widget = Dropdown(**self.__data())
        self.__hover  = hover
        self.__observe(action, tick1, tick2)
        return Paragraph(text = self.getCSS().title.sequence.get()), self.__widget

    def update(self):
        "updates the widget"
        self.__widget.update(**self.__data())

    def __data(self) -> dict:
        lst = self.__list
        lst.clear()
        lst.extend(sorted(readsequence(self._model.sequencepath).keys()))

        key   = self._model.sequencekey
        val   = key if key in lst else None
        menu  = [(i, i) for i in lst] if len(lst) else []  # type: List[Optional[Tuple[str,str]]]
        if len(menu):
            title = self.getCSS().title.sequence.missing.key.get()
            menu += [None, (title, '←')]
        else:
            title = self.getCSS().title.sequence.missing.path.get()
            menu += [('', '→'), (title, '←')]
        return dict(menu  = menu,
                    label = title if val is None else key,
                    value = '→'   if val is None else val)

    def __observe(self, action, tick1, tick2):
        def _py_cb(new):
            if new in self.__list:
                self._model.sequencekey = new
            elif new == '←':
                path = self.__dialog.open()
                seqs = readsequence(path)
                if len(seqs) > 0:
                    self._model.sequencepath = path
                    self._model.sequencekey  = next(iter(seqs))
                else:
                    self.__widget.value = '→'
        self.__widget.on_click(action(_py_cb))

        widget = self.__widget
        hover  = self.__hover
        src    = hover.source('hist')
        def _js_cb(choice  = widget, tick1 = tick1, tick2 = tick2, src = src):
            if choice.value in src.column_names:
                choice.label     = choice.value
                tick1.key        = choice.value
                tick2.key        = choice.value
                src.data['text'] = src.data[choice.value]
                src.trigger("change")
        self.__widget.js_on_change('value', CustomJS.from_py_func(_js_cb))

        self.getConfig().observe(('sequence.key', 'sequence.path'),
                                 lambda: self.__widget.update(**self.__data()))

class _OligosCreator(WidgetCreator):
    "Oligo list creator"
    def __init__(self, ctrl:Controller, model:TrackPlotModelController, key:str) -> None:
        super().__init__(ctrl, model, key)
        self.__widget  = None # type: Optional[TextInput]
        self.getCSS().defaults = {'title.oligos'     : u'Oligos',
                                  'title.oligos.help': u'comma-separated list'}

    def create(self, action):
        "creates the widget"
        self.__widget = TextInput(value       = self.__data(),
                                  placeholder = self.getCSS().title.oligos.help.get(),
                                  title       = self.getCSS().title.oligos.get())
        self.__observe(action)
        return self.__widget

    def update(self):
        "updates the widget"
        self.__widget.value = self.__data()

    def __data(self):
        return ', '.join(sorted(j.lower() for j in self._model.oligos))

    def __observe(self, action):
        widget = self.__widget
        match  = re.compile(r'(?:[^atgc]*)([atgc]+)(?:[^atgc]+|$)*',
                            re.IGNORECASE).findall
        def _py_cb(attr, old, new):
            self._model.oligos = sorted({i.lower() for i in match(new)})
        widget.on_change('value', action(_py_cb))

        self.getConfig().observe('oligos', lambda: setattr(self.__widget, 'value',
                                                           self.__data()))

class _ConfigMixin(_Mixin):
    def __init__(self):
        args           = self._ctrl, self._model, self.key('')
        self.__table   = _PeakTableCreator(*args)
        self.__sliders = _SliderCreator(*args)
        self.__seq     = _SequenceCreator(*args)
        self.__oligs   = _OligosCreator(*args)

    def _createconfig(self):
        stretch, bias  = self.__sliders.create(self._histsource)
        par,     table = self.__table  .create(self._hover)
        oligos         = self.__oligs  .create(self.action)
        parseq,  seq   = self.__seq    .create(self.action, self._hover,
                                               self._gridticker,
                                               self._gridticker.getaxis())

        self.__sliders.callbacks(self.action, self._hover, table)
        self.__table  .callbacks(self.action, stretch, bias)
        ret = layouts.layout([[layouts.widgetbox([parseq, seq]), oligos],
                              [layouts.widgetbox([bias, stretch]),
                               layouts.widgetbox([par,  table])]])

        enableOnTrack(self, self._hist, self._raw, stretch, bias, oligos, seq, table)
        return ret

    def _updateconfig(self):
        self.__sliders.update()
        self.__table.update()
        self.__oligs.update()
        self.__seq.update()

class CyclesPlotCreator(TrackPlotCreator, _HistMixin, _RawMixin, _ConfigMixin):
    "Displays cycles and their projection"
    _MODEL = CyclesModelController
    def __init__(self,  ctrl:Controller) -> None:
        "sets up this plotter's info"
        TrackPlotCreator.__init__(self, ctrl)
        _RawMixin       .__init__(self)
        _HistMixin      .__init__(self)
        _ConfigMixin    .__init__(self)
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
