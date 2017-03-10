#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Cycles plot view"

from typing         import (Optional, # pylint: disable=unused-import
                            TYPE_CHECKING)
from itertools      import product

from bokeh.model    import Model
from bokeh.core.properties  import Float, Seq, Instance, Bool
from bokeh.plotting import figure, Figure # pylint: disable=unused-import
from bokeh.layouts  import gridplot
from bokeh.models   import (LinearAxis, ColumnDataSource, HoverTool,
                            CustomJS, Range1d, ContinuousTicker,
                            BasicTicker, Ticker)

import numpy        as np

import sequences
from   control      import Controller
from  .plotutils    import (PlotAttrs, DpxKeyedRow,
                            TrackPlotCreator, TrackPlotView,
                            checksizes, readsequence)

window = None # type: ignore # pylint: disable=invalid-name

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

    @staticmethod
    def defaultconfig() -> dict:
        "default config"
        return dict(selraw      = PlotAttrs('green', 'line',   2),
                    tooltips    = [(u'(cycle, t, z)', '(@cycles, $~x, $data_y)')],
                    sequences   = "../tests/testingcore/hairpins.fasta",
                    sequencekey = 'GF1')

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

    def createraw(self, fig, source, data, cnf):
        "creates the hover tool"
        self.precision = cnf.binwidth.get()
        self.bias      = cnf.basebias.get()
        self.slope     = cnf.baseslope.get()

        hover          = fig.select(HoverTool)
        if len(hover) == 0:
            return
        attrs          = cnf['selraw'].get()

        glyph = attrs.addto(fig, x = 't', y = 'sel', source = source, visible = False)
        def _onhover(source = source, glyph = glyph, mdl = self, cb_data = None):
            xval = window.Math.floor(cb_data['geometry'].x+0.5)
            yval = cb_data['geometry'].y
            dist = mdl.precision
            best = None
            for column in source.column_names:
                tmp = window.Math.abs(source.data[column][xval] - yval)
                if tmp < dist:
                    dist = tmp
                    best = column

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

        tooltips  = cnf['tooltips'].get()
        if tooltips is None or len(tooltips) == 0:
            return

        self._rawsource = ColumnDataSource(self._createrawdata(data))
        hover[0].tooltips  = tooltips
        hover[0].renderers = [fig.circle(x                = 'inds',
                                         y                = 'values',
                                         source           = self._rawsource,
                                         radius           = 2,
                                         radius_dimension = 'x',
                                         line_alpha       = 0.,
                                         fill_alpha       = 0.,
                                         visible          = False)]

    @staticmethod
    @checksizes
    def _createhistdata(cnf):
        key   = cnf.sequencekey.get()
        oligs = cnf.oligos.get()
        osiz  = max(len(i) for i in oligs)
        dseq  = readsequence(cnf)
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

    def createhist(self, fig, cnf):
        "Creates the hover tool for histograms"
        self.update(framerate = 1./30.,
                    bias      = 0.,
                    slope     = cnf.baseslope.get())

        hover = fig.select(HoverTool)
        if len(hover) == 0:
            return

        self._histsource = ColumnDataSource(self._createhistdata(cnf))
        hover[0].tooltips   = '@values: @text'
        hover[0].mode       = 'hline'

        hover[0].renderers  = [fig.circle(x                = 'inds',
                                          y                = 'values',
                                          source           = self._histsource,
                                          radius           = 1.5,
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

    def updatehist(self, fig, track, hdata, cnf):
        "updates the tooltips for a new file"
        hover = fig.select(HoverTool)
        if len(hover) == 0:
            return

        self._histsource.data = self._createhistdata(cnf)
        bias  = cnf.basebias.get()
        if bias is None:
            ind  = next((i for i,j in enumerate(hdata['cycles']) if j > 0), 0)
            bias = hdata['bottom'][ind] + cnf.binwidth.get()*.5

        self.update(framerate = track.framerate,
                    bias      = bias,
                    slope     = cnf.baseslope.get())

class DpxFixedTicker(ContinuousTicker):
    "Generate ticks at fixed, explicitly supplied locations."

    major   = Seq(Float, default=[], help="List of major tick locations.")
    minor   = Seq(Float, default=[], help="List of major tick locations.")
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
                major:   [ p.Array, [] ]
                minor:   [ p.Array, [] ]
                usebase: [ p.Bool,     true]
                base:    [ p.Instance, null]
            }

            get_ticks_no_defaults: (data_low, data_high, desired_n_ticks) ->
                if @usebase
                    return @base.get_ticks_no_defaults(data_low, data_high,
                                                       desired_n_ticks)
                return {
                    major: @major
                    minor: @minor
                }
    """
    def __init__(self, **kwa):
        super().__init__(**kwa)
        self._defaults = []     # type: list
        self._axis     = None   # type: Optional[DpxFixedTicker]

    def create(self, cnf, *figs):
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
                                  axis_label   = cnf.hist.ylabel.get(),
                                  ticker       = self._axis),
                       'right')
    @staticmethod
    def defaultconfig() -> dict:
        "default config"
        return dict(gridcolor = ('lightblue', 'lightgreen'),
                    gridwidth = (2,           2),
                    gridalpha = (1.,          1.),
                    griddash  = ('solid',     'solid'))

    def update(self, cnf, *figs):
        "Updates the ticks according to the configuration"
        dseq = readsequence(cnf)
        seq  = dseq.get(cnf.sequencekey.get(), next(iter(dseq.values()), None))

        self.usebase = seq is None
        if self._axis:
            self._axis.usebase = self.usebase
        if self.usebase:
            for (fig, name), val in zip(product(figs, self._ORDER), self._defaults):
                setattr(fig.ygrid[0], name, val)
        else:
            peaks      = sequences.peaks(seq, cnf.oligos.get())
            self.major = tuple(peaks["position"][peaks['orientation']])
            self.minor = tuple(peaks["position"][~peaks['orientation']])
            if self._axis:
                self._axis.major = self.major + self.minor
                self._axis.minor = []

            for fig in figs:
                grd = fig.ygrid[0]
                grd.y_range_name = 'bases'
                for name in ('color', 'dash', 'width', 'alpha'):
                    props = cnf['grid'+name].get()
                    setattr(grd, 'grid_line_'+name,       props[0])
                    setattr(grd, 'minor_grid_line_'+name, props[1])

class _Mixin:
    if TYPE_CHECKING:
        # pylint: disable=no-self-use,unused-argument
        def getConfig(self):
            "returns the config"
            return

        def key(self):
            "returns the plot key"
            return ''

        def _figargs(self, cnf, width, loc):
            "returns figure args"
            return

class _RawMixin(_Mixin):
    def __init__(self):
        "sets up this plotter's info"
        self.getConfig().defaults = dict(raw = PlotAttrs('blue',  'circle', 1,
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
        cnf             = self.getConfig()
        self._raw       = figure(y_axis_label = self.getConfig().ylabel.get(),
                                 y_range      = Range1d(start = 0., end = 1.),
                                 **self._figargs(cnf, 500, 'left'))
        raw             = self._createrawdata(track, bead)
        self._rawsource = ColumnDataSource(data = raw)

        for ind, attrs in enumerate(cnf.raw.get().iterpalette(cnf.ncycles.get())):
            attrs.addto(self._raw,
                        x       = 't',
                        y       = 'C%d' % ind,
                        source  = self._rawsource,
                        tags    = ['__lines__'],
                        visible = raw['t'] is not raw['C%d' % ind])

        self._hover.createraw(self._raw, self._rawsource, raw, cnf)
        self._raw.extra_x_ranges = {"time": Range1d(start = 0., end = 1.)}

        axis = LinearAxis(x_range_name="time", axis_label = cnf.xtoplabel.get())
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
        cnf = self.getConfig()
        cnf.defaults = dict(binwidth  = .003,
                            minframes = 10,
                            basebias  = None,
                            baseslope = 8.8e-4,
                            frames    = PlotAttrs('white', 'quad',   1,
                                                  line_color = 'gray',
                                                  fill_color = 'gray'),
                            cycles    = PlotAttrs('white', 'quad',   1,
                                                  fill_color = None,
                                                  line_alpha = .5,
                                                  line_color = 'blue'),

                            **DpxFixedTicker.defaultconfig()
                           )
        cnf.hist.defaults = dict(xtoplabel = u'Cycles',
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
            width = self.getConfig()["binwidth"].get()
            bins  = np.arange(rng[0]-width*.5, rng[1]+width*1.01, width, dtype = 'f4')
            if bins[-2] > rng[1]:
                bins = bins[:-1]

            items = [np.bincount(np.digitize(i, bins), minlength = len(bins))[1:]
                     for i in items]
            zeros = np.zeros((len(bins)-1,), dtype = 'f4')

        threshold = self.getConfig()['minframes'].get()
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
        cnf              = self.getConfig()
        self._hist       = figure(y_axis_location = None,
                                  y_range         = yrng,
                                  **self._figargs(cnf.hist, 200, None))

        hist             = self._createhistdata(track, bead)
        self._histsource = ColumnDataSource(data = hist)

        self._hist.extra_x_ranges = {"cycles": Range1d(start = 0., end = 1.)}

        attrs = cnf.cycles.get()
        axis  = LinearAxis(x_range_name          = "cycles",
                           axis_label            = cnf.hist.xtoplabel.get(),
                           axis_label_text_color = attrs.line_color
                          )
        self._hist.add_layout(axis, 'above')

        cnf.frames.addto(self._hist,
                         source = self._histsource,
                         bottom = "bottom", top   = "top",
                         left   = "left",   right = "frames")

        attrs.addto(self._hist,
                    source = self._histsource,
                    bottom = "bottom", top   = "top",
                    left   = "left",   right = "cycles",
                    x_range_name = "cycles")

        self._gridticker = DpxFixedTicker()
        self._gridticker.create(self.getConfig(), self._hist)
        self._hover.createhist(self._hist, self.getConfig())
        self._slavexaxis()

    def _updatehist(self, track, bead):
        self._hist.disabled   = False
        self._histsource.data = hist = self._createhistdata(track, bead)
        self._hover.updatehist(self._hist, track, hist, self.getConfig())
        self.setbounds(self._hist.y_range, 'y', (hist['bottom'][0], hist['top'][-1]))
        self._gridticker.update(self.getConfig(), self._hist)

class CyclesPlotCreator(TrackPlotCreator, _HistMixin, _RawMixin):
    "Displays cycles and their projection"
    def __init__(self,  ctrl:Controller) -> None:
        "sets up this plotter's info"
        TrackPlotCreator.__init__(self, ctrl)
        _RawMixin       .__init__(self)
        _HistMixin      .__init__(self)
        self.getConfig().defaults = dict(tools   = 'ypan,ybox_zoom,reset,save,hover',
                                         ncycles = 150,
                                         oligos  = ['CTGT'],
                                         **DpxHoverModel.defaultconfig())
        self._hover  = None # type: Optional[DpxHoverModel]

    def _figargs(self, cnf, width, loc): # pylint: disable=arguments-differ
        args = super()._figargs()
        args['x_axis_label']     = cnf.xlabel.get()
        args['plot_width']       = width
        args['toolbar_location'] = loc
        return args

    def _create(self, track, bead) -> DpxKeyedRow:
        "returns the figure"
        self._hover  = DpxHoverModel()
        self._createraw(track, bead)
        self._createhist(track, bead, self._raw.y_range)
        row = gridplot([[self._raw, self._hist]])

        return DpxKeyedRow(self, self._raw,
                           children = [row],
                           toolbar  = row.children[0])

    def _update(self, track, bead):
        self._updateraw(track, bead)
        self._updatehist(track, bead)

class CyclesPlotView(TrackPlotView):
    "Cycles plot view"
    PLOTTTER = CyclesPlotCreator
