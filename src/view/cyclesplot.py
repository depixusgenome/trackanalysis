#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Cycles plot view"

from typing         import (Optional, # pylint: disable=unused-import
                            Sequence, Tuple, cast, TYPE_CHECKING)
from itertools      import product
import re

from bokeh          import layouts
from bokeh.model    import Model
from bokeh.core.properties  import Float, Seq, Instance, Bool, Dict, String
from bokeh.plotting import figure, Figure # pylint: disable=unused-import
from bokeh.models   import (LinearAxis, ColumnDataSource, HoverTool,
                            CustomJS, Range1d, ContinuousTicker,
                            BasicTicker, Ticker, Dropdown, TextInput,
                            DataTable, TableColumn, IntEditor, NumberEditor,
                            Paragraph)

import numpy        as np

import sequences
from   utils                  import NoArgs
from   control                import Controller
from  .dialog                 import FileDialog
from  .plotutils              import (PlotAttrs, DpxKeyedRow, TrackPlotCreator,
                                      TrackPlotView, TrackPlotModel, checksizes,
                                      readsequence)

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
    _CACHED = 'base.slope', 'base.bias', 'sequence.key', 'sequence.witnesses'
    def __init__(self, ctrl, cnf, curr):
        super().__init__(ctrl, cnf, curr)
        cnf.defaults = {'binwidth'      : .003,
                        'minframes'     : 10,
                        'base.bias'     : None,
                        'base.slope'    : 8.8e-4,
                        'sequence.path' : "../tests/testingcore/hairpins.fasta",
                        'sequence.key'  : 'GF1',
                       }
        cnf.sequence.witnesses.default = None
        for attr in self._CACHED:
            self.curr[attr].setdefault(None)
        self.update()

    def update(self):
        u"updates the model when a new track is loaded"
        self.curr.update({i: dict() for i in self._CACHED})

    binwidth     = cast(float,                   configprop  ('binwidth'))
    minframes    = cast(int,                     configprop  ('minframes'))
    sequencepath = cast(Optional[str],           configprop  ('sequence.path'))
    oligos       = cast(Optional[Sequence[str]], configprop  ('oligos'))
    slope        = cast(float,                   beadorconfig('base.slope'))
    bias         = cast(Optional[float],         beadorconfig('base.bias'))
    sequencekey  = cast(Optional[str],           beadorconfig('sequence.key'))
    witnesses    = cast(Optional[Tuple[float,float,float,float]],
                        beadorconfig('sequence.witnesses'))

class DpxHoverModel(Model):
    "controls keypress actions"
    precision = Float(0.003)
    framerate = Float(1.)
    bias      = Float(0.)
    slope     = Float(0.)
    __implementation__ = """
    import * as p  from "core/properties"
    import {Model} from "model"

    export class DpxHoverModelView
    export class DpxHoverModel extends Model
        default_view: DpxHoverModelView
        type:"DpxHoverModel"
        @define {
            precision : [p.Number, 0.003],
            framerate : [p.Number, 1],
            slope     : [p.Number, 0],
            bias      : [p.Number, 0]
        }
    """
    def __init__(self, **kwa):
        super().__init__(**kwa)
        self._rawsource  = ColumnDataSource()
        self._histsource = ColumnDataSource()

    def source(self, key):
        u"returns the hist source"
        return getattr(self, '_'+key+'source')

    @staticmethod
    def defaultconfig() -> dict:
        "default config"
        return {'raw.selection'       : PlotAttrs('green', 'line',   2),
                'raw.tooltips'        : [(u'(cycle, t, z)', '(@cycles, $~x, $data_y)')],
                'raw.tooltips.radius' : 2,
                'hist.tooltips.radius': 1.5
               }

    @staticmethod
    @checksizes
    def _createrawdata(raw):
        get     = lambda i: raw['C%d'%i]
        time    = raw['t']
        ncycles = sum(i.startswith('C') for i in raw)

        sizes   = [np.isfinite(get(i)) for i in range(ncycles) if get(i) is not time]
        if len(sizes) == 0:
            return dict(values = [0], inds = [0], cycles = [0])

        vals    = np.concatenate([get(i)[j] for i, j in enumerate(sizes)])
        inds    = np.concatenate([np.arange(len(j))[j] for    j in sizes])
        cycles  = np.concatenate([np.full((j.sum(),), i, dtype = 'i4')
                                  for i, j in enumerate(sizes)])
        data    = dict(values = vals, inds   = inds, cycles = cycles)
        return data

    def createraw(self, fig, source, data, mdl, css): # pylint: disable = too-many-arguments
        "creates the hover tool"
        self.precision = mdl.binwidth
        self.bias      = mdl.bias
        self.slope     = mdl.slope

        hover          = fig.select(HoverTool)
        if len(hover) == 0:
            return
        attrs          = css.raw.selection.get()

        glyph = attrs.addto(fig, x = 't', y = 'sel', source = source, visible = False)
        def _onhover(source = source, glyph = glyph, mdl = self, cb_data = None):
            xval = window.Math.floor(cb_data['geometry'].x+0.5)
            yval = cb_data['geometry'].y
            dist = mdl.precision
            best = None
            for col in source.column_names:
                tmp = window.Math.abs(source.data[col][xval] - yval)
                if tmp < dist:
                    dist = tmp
                    best = col

            if best is not None:
                source.data['sel'] = source.data[best]
                glyph.glyph.visible = True
                source.trigger("change")
                glyph.trigger("change")
            elif glyph.glyph.visible:
                glyph.glyph.visible = False
                glyph.trigger("change")

        hover[0].callback  = CustomJS.from_py_func(_onhover)
        hover[0].tooltips  = None

        tooltips  = css.raw.tooltips.get()
        if tooltips is None or len(tooltips) == 0:
            return

        self._rawsource = ColumnDataSource(self._createrawdata(data))
        hover[0].tooltips  = tooltips
        hover[0].renderers = [fig.circle(x                = 'inds',
                                         y                = 'values',
                                         source           = self._rawsource,
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
        return data

    def createhist(self, fig, mdl, css):
        "Creates the hover tool for histograms"
        self.update(framerate = 1./30.,
                    bias      = 0.,
                    slope     = mdl.slope)

        hover = fig.select(HoverTool)
        if len(hover) == 0:
            return

        self._histsource = ColumnDataSource(self._createhistdata(mdl))
        hover[0].tooltips   = '@values: @text'
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

    def updateraw(self, fig, rdata):
        "updates the tooltips for a new file"
        hover = fig.select(HoverTool)
        if len(hover) == 0:
            return

        self._rawsource.data  = self._createrawdata(rdata)

    def updatehist(self, fig, hdata, mdl):
        "updates the tooltips for a new file"
        hover = fig.select(HoverTool)
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
                    slope     = mdl.slope)

    def observe(self, ctrl, key, mdl):
        u"sets up model observers"
        def _onconfig(items):
            if 'oligos' in items:
                self._histsource.data = self._createhistdata(mdl)

        ctrl.observe(key, _onconfig)

class DpxFixedTicker(ContinuousTicker):
    "Generate ticks at fixed, explicitly supplied locations."

    major   = Dict(String, Seq(Float), default = {'': []})
    minor   = Dict(String, Seq(Float), default = {'': []})
    key     = String(default = '')
    usebase = Bool(default = True)
    base    = Instance(Ticker, default = BasicTicker())

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
                    props = css['grid'+name].get()
                    setattr(grd, 'grid_line_'+name,       props[0])
                    setattr(grd, 'minor_grid_line_'+name, props[1])

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

        def _figargs(self, cnf, width, loc):
            "returns figure args"
            return

class _RawMixin(_Mixin):
    def __init__(self):
        "sets up this plotter's info"
        self.getCSS().defaults = dict(raw = PlotAttrs('blue',  'circle', 1,
                                                      alpha   = .5,
                                                      palette = 'inferno'))
        self._rawsource = None # type: Optional[ColumnDataSource]
        self._raw       = None # type: Optional[Figure]

    @checksizes
    def _createrawdata(self, track, bead) -> dict:
        keys        = set('C%d' % i for i in range(self.getConfig().ncycles.get()))
        if track is None:
            return dict.fromkeys(('t', 'sel')+tuple(keys), [0., 1.])
        items = dict(('C%d' % i[-1], j) for i, j in track.cycles[bead,...])
        sizes = {len(i) for i in items.values()}
        size  = max(sizes)
        if len(sizes) > 1:
            nans = np.full((size,), np.NaN, dtype = 'f4')
            for i, j in items.items():
                if len(j) == size:
                    continue
                items[i] = np.concatenate((j, nans[:size-len(j)]))

        items['t']    = np.arange(size, dtype = 'f4')
        items.update(dict.fromkeys(keys - set(items.keys()), items['t'])) # type: ignore
        items['sel']  = items['C0']
        return items

    def _addrawcallbacks(self):
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
        cnf             = self.getConfig()
        self._raw       = figure(y_axis_label = css.ylabel.get(),
                                 y_range      = Range1d(start = 0., end = 1.),
                                 **self._figargs(css, 500, 'left'))
        raw             = self._createrawdata(track, bead)
        self._rawsource = ColumnDataSource(data = raw)

        for ind, attrs in enumerate(css.raw.get().iterpalette(cnf.ncycles.get())):
            attrs.addto(self._raw,
                        x       = 't',
                        y       = 'C%d' % ind,
                        source  = self._rawsource,
                        tags    = ['__lines__'],
                        visible = raw['t'] is not raw['C%d' % ind])

        self._hover.createraw(self._raw, self._rawsource, raw, self._model, self.getCSS())
        self._raw.extra_x_ranges = {"time": Range1d(start = 0., end = 1.)}

        axis = LinearAxis(x_range_name="time", axis_label = css.xtoplabel.get())
        self._raw.add_layout(axis, 'above')

    def _updateraw(self, track, bead):
        self._raw.disabled    = False
        self._rawsource.data  = raw = self._createrawdata(track, bead)
        for glyph in self._raw.select(tags = '__lines__'):
            glyph.visible = raw[glyph.y] is not raw['t']
        self._hover.updateraw(self._raw, raw)

class _HistMixin(_Mixin):
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
                                 ylabel    = u'Base number')

        self._histsource = None # type: Optional[ColumnDataSource]
        self._hist       = None # type: Optional[Figure]
        self._gridticker = None # type: Optional[DpxFixedTicker]

    @checksizes
    def _createhistdata(self, track, bead):
        if track is None:
            bins  = np.array([-1, 1])
            zeros = np.zeros((1,), dtype = 'f4')
            items = zeros,
        else:
            items = [i for _, i in track.cycles[bead,...].withphases(5,5)]
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
            bases.start  = (yrng.start-mdl.bias)/mdl.slope
            bases.end    = (yrng.end-mdl.bias)/mdl.slope

            bottom = src.data["bottom"]
            delta  = bottom[1]-bottom[0]

            ind1   = min(len(bottom), max(0, int((yrng.start-bottom[0])/delta-1)))
            ind2   = min(len(bottom), max(0, int((yrng.end  -bottom[0])/delta+1)))

            if ind1 >= ind2:
                return

            frames.end = window.Math.max.apply(None, src.data['frames'][ind1:ind2])+1
            cycles.end = window.Math.max.apply(None, src.data['cycles'][ind1:ind2])+1

        self._hist.y_range.callback = CustomJS.from_py_func(_onchangebounds)

    def _createhist(self, track, bead, yrng):
        css              = self.getCSS()
        self._hist       = figure(y_axis_location = None,
                                  y_range         = yrng,
                                  **self._figargs(css.hist, 200, None))

        hist             = self._createhistdata(track, bead)
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

    def _updatehist(self, track, bead):
        self._hist.disabled   = False
        self._histsource.data = hist = self._createhistdata(track, bead)
        self._hover.updatehist(self._hist, hist, self._model)
        self.setbounds(self._hist.y_range, 'y', (hist['bottom'][0], hist['top'][-1]))
        self._gridticker.updatedata(self._model, self.getCSS(), self._hist)

class _ConfigMixin(_Mixin):
    def __init__(self):
        self.__updates = [] # type: List[Callable]
        self.getCSS().defaults = {'tablesize'      : (200, 100),
                                  'title.table'    : u'[nm] ↔ [base] in positions',
                                  'title.sequence' : u'Selected DNA sequence',
                                  'title.slope'    : u'[nm] ↔ [base] slope',
                                  'title.bias'     : u'[nm] ↔ [base] bias'}

    def _createconfig(self):
        self.__observemodel()
        return layouts.layout([[layouts.widgetbox(list(self.__doconvert())),
                                layouts.widgetbox(list(self.__dowitness()))],
                               [layouts.widgetbox(list(self.__dosequence())),
                                self.__dooligos ()]])

    def _updateconfig(self):
        for fcn in self.__updates:
            fcn()

    def __observemodel(self):
        def _py_cb(attr, old, new):
            setattr(self._model, attr, new)

        def _js_cb(fig = self._hist, mdl = self._hover):
            zrng       = fig.y_range
            brng       = fig.extra_y_ranges['bases']
            brng.start = (zrng.start - mdl.bias)/mdl.slope
            brng.end   = (zrng.end   - mdl.bias)/mdl.slope

        for name in 'slope', 'bias':
            self._hover.on_change(name,    _py_cb)
            self._hover.js_on_change(name, CustomJS.from_py_func(_js_cb))

    def __doconvert(self):
        css   = self.getCSS().title
        slope = TextInput(value = str(self._model.slope), title = css.slope.get())
        bias  = TextInput(value = str(self._hover.bias),  title = css.bias .get())
        def _js_cb(slope = slope, bias = bias, mdl = self._hover):
            mdl.slope  = float(slope.value)
            mdl.bias   = float(bias.value)

        for widget in (slope, bias):
            widget.js_on_change('value', CustomJS.from_py_func(_js_cb))

        def _onupdate():
            slope.value = str(self._model.slope)
            bias.value  = str(self._model.bias)

        def _onconfig(items):
            if any(i in items  for i in ('base.slope', 'base.bias')):
                _onupdate()

        self._ctrl.observe(self.key(),          _onconfig)
        self._ctrl.observe(self.key("current"), _onconfig)
        self.__updates.append(_onupdate)
        return slope, bias

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
                            peaks[0] *self._hover.slope+self._hover.bias,
                            peaks[-1]*self._hover.slope+self._hover.bias)
            if info is None:
                info = (0., 1e3, self._hover.bias, self._hover.slope)
            return dict(bases = info[:2], frames = info[2:])

        size = self.getCSS().tablesize.get()
        data = ColumnDataSource(_createdata())
        cols = [TableColumn(field  = 'bases',
                            title  = self.getCSS().hist.ylabel.get(),
                            editor = IntEditor(),
                            width  = size[0]//2),
                TableColumn(field  = 'frames',
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
            self._model.witnesses = tuple(data.data['bases']) + tuple(data.data['cycles'])
        data.on_change("data", self.action(_py_cb))

        def _js_cb(mdl = self._hover, data = data):
            cycles   = data.data['cycles']
            if cycles[0] == cycles[1]:
                return
            bases    = data.data['bases']
            if bases[0] == bases[1]:
                return
            slope     = (cycles[1]-cycles[0]) / (bases[1]-bases[0])
            bias      = cycles[0] - bases[0]*slope
            mdl.slope = slope
            mdl.bias  = bias
        data.js_on_change("data", CustomJS.from_py_func(_js_cb))

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
            lst.extend(sorted(readsequence(self._model.sequencepath).items()))
            if len(lst) == 0:
                lst = [('→', '--1--')]
            key = self._model.sequencekey
            val = next((j for i, j in lst if i == key), None)

            return dict(menu  = ([(j, str(i)) for i, (j, _) in enumerate(lst)]
                                 + [None, (u'Find path', '--2--')]),
                        label = u'Sequence' if val is None else key,
                        value = u'--1--'    if val is None else val)

        widget = Dropdown(**_attrs())

        def _py_cb(new):
            if new not in ('--1--', '--2--'):
                self._model.sequencekey = lst[int(new)]
            else:
                path = dia.open()
                seqs = readsequence(path)
                if len(seqs) > 0:
                    self._model.sequencepath = path
                    self._model.sequencekey  = next(iter(seqs))

        def _js_cb(choice = widget,
                   ticker = self._gridticker,
                   hsrc   = self._histsource,
                   tsrc   = self._hover.source('hist')):
            if choice.value not in ('--1--', '--2--'):
                ticker.key        = choice.value
                tsrc.data['text'] = tsrc.data[choice.value]
                tsrc.trigger('change')
                hsrc.trigger('change')

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
        self.getCSS   ().defaults = DpxHoverModel.defaultconfig()
        self.getConfig().defaults = dict(tools   = 'ypan,ybox_zoom,reset,save,hover',
                                         ncycles = 150,
                                         oligos  = ['CTGT'])
        self._hover  = None # type: Optional[DpxHoverModel]

    def _figargs(self, css, width, loc): # pylint: disable=arguments-differ
        args = super()._figargs()
        args['x_axis_label']     = css.xlabel.get()
        args['plot_width']       = width
        args['toolbar_location'] = loc
        return args

    def _create(self, track, bead) -> DpxKeyedRow:
        "returns the figure"
        self._hover  = DpxHoverModel()
        self._createraw(track, bead)
        self._createhist(track, bead, self._raw.y_range)
        plts  = layouts.gridplot([[self._raw, self._hist]])
        items = layouts.column([plts, self._createconfig()])

        return DpxKeyedRow(self, self._raw,
                           children = [items],
                           toolbar  = plts.children[0])

    def _update(self, track, bead, items):
        if 'track' in items:
            self._model.update() # pylint: disable=no-member
        self._updateraw(track, bead)
        self._updatehist(track, bead)
        self._updateconfig()

class CyclesPlotView(TrackPlotView):
    "Cycles plot view"
    PLOTTER = CyclesPlotCreator
