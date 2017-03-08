#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Track plot view"

from typing         import (Optional, # pylint: disable=unused-import
                            TYPE_CHECKING)
from pathlib        import Path
from functools      import wraps

from bokeh.model    import Model
from bokeh.core.properties  import Float
from bokeh.plotting import figure
from bokeh.layouts  import gridplot
from bokeh.models   import (LinearAxis, ColumnDataSource, HoverTool,
                            CustomJS, Range1d)

import numpy        as np

import sequences
from control        import Controller
from .plotutils     import PlotAttrs, Plotter, DpxKeyedRow
from .              import BokehView

window = None # type: ignore # pylint: disable=invalid-name

def _checksizes(fcn):
    @wraps(fcn)
    def _wrap(*args, **kwa):
        res  = fcn(*args, **kwa)
        if len(res) == 0:
            return res
        size = len(next(iter(res.values())))
        assert all(size == len(i) for i in res.values())
        return res
    return _wrap

class _TrackPlotter(Plotter):
    _row = None # type: Optional[DpxKeyedRow]
    def __init__(self, *_):
        super().__init__(*_)
        self._row = None

    def create(self) -> DpxKeyedRow:
        u"returns the figure"
        self._row   = self._create(*self._gettrack())
        self._row.disabled = True
        return self._row

    def update(self, items:dict):
        "Updates the data"
        if not ('track' in items or 'bead' in items):
            return

        with self.updating():
            self._row.disabled = False
            self._update(*self._gettrack())

    def _create(self, track, bead) -> DpxKeyedRow:
        raise NotImplementedError()

    def _update(self, track, bead):
        raise NotImplementedError()

    def _gettrack(self):
        cnf  = self._ctrl.getGlobal("current")
        task = cnf.track.get(default = None)
        if task is None:
            return None, None

        track = self._ctrl.track(task)
        bead  = cnf.bead.get(default = None)
        if bead is None:
            bead = next(iter(track.beadsonly.keys()))
        return track, bead

class BeadPlotter(_TrackPlotter):
    "Plots a default bead"
    def __init__(self,  ctrl:Controller) -> None:
        "sets up this plotter's info"
        super().__init__(ctrl)
        self._source = ColumnDataSource()
        self._fig    = figure(**self._figargs())

        cnf = ctrl.getGlobal(self.key())
        cnf.defaults = dict(z        = PlotAttrs('blue', 'circle', 1),
                            zmag     = PlotAttrs('red',  'line',   1),
                            tooltips = [(u'Index',  '$index'),
                                        (u'(t, z, zmag)', '($data_x, $data_y, @zmag)')])

    def _get(self, name):
        return self._source.data[name] # pylint: disable=unsubscriptable-object

    @staticmethod
    def _createdata(track, bead):
        if track is None:
            return dict.fromkeys(('t', 'zmag', 'z'), [0., 1.])
        items       = track.beads
        return dict(t    = items['t'],
                    zmag = items['zmag'],
                    z    = items[bead])

    def _figargs(self):
        args = super()._figargs()
        if self.getConfig().tooltips.get() not in ('', None):
            args['tools'] += ',hover'
        args.update(x_axis_label = u'Frames',
                    y_axis_label = u'z',
                    x_range      = Range1d(start = 0., end = 1.),
                    y_range      = Range1d(start = 0., end = 1.))
        return args

    def _addglyph(self, beadname, **kwa):
        return self.getConfig()[beadname].addto(self._fig,
                                                x      = 't',
                                                y      = beadname,
                                                source = self._source,
                                                **kwa)

    def _addylayout(self):
        self._fig.extra_y_ranges = {'zmag': Range1d(start = 0., end = 1.)}
        self._fig.add_layout(LinearAxis(y_range_name='zmag', axis_label = u'zmag'), 'right')

    def _addcallbacks(self, fig):
        super()._addcallbacks(fig)
        rng = self._fig.extra_y_ranges['zmag']
        def _onRangeChange(rng = rng):
            rng.start = rng.bounds[0]
            rng.end   = rng.bounds[1]

        rng.callback = CustomJS.from_py_func(_onRangeChange)

    def _setbounds(self):
        self.setbounds(self._fig.extra_y_ranges['zmag'], None, self._get('zmag'))
        self.setbounds(self._fig.x_range, 'x', self._get('t'))
        self.setbounds(self._fig.y_range, 'y', self._get('z'))

    def _create(self, track, bead) -> DpxKeyedRow:
        "sets-up the figure"
        self._source = ColumnDataSource(data = self._createdata(track, bead))
        if self.getConfig().tooltips.get() not in ('', None):
            self._fig.select(HoverTool).tooltips = self.getConfig().tooltips.get()

        self._addylayout  ()
        self._addglyph    ("zmag", y_range_name = 'zmag')

        self._addglyph    ("z")
        for rng in self._fig.x_range, self._fig.y_range, self._fig.extra_y_ranges['zmag']:
            self.fixreset(rng)

        self._addcallbacks(self._fig)
        return DpxKeyedRow(self, self._fig)

    def _update(self, track, bead):
        self._fig.disabled = False
        self._source.data  = self._createdata(track, bead)
        self._setbounds()

class DpxHoverModel(Model):
    u"controls keypress actions"
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
        u"default config"
        return dict(selraw      = PlotAttrs('green', 'line',   2),
                    tooltips    = [(u'(cycle, t, z)', '(@cycles, $~x, $~y)')],
                    sequences   = "../tests/testingcore/hairpins.fasta",
                    oligosize   = 4,
                    sequencekey = 'GF1')

    @staticmethod
    @_checksizes
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
        u"creates the hover tool"
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
                                         radius           = 1.,
                                         radius_dimension = 'x',
                                         line_alpha       = 0.,
                                         fill_alpha       = 0.,
                                         visible          = False)]

    @staticmethod
    @_checksizes
    def _createhistdata(cnf):
        path = cnf.sequences.get()
        key  = cnf.sequencekey.get()
        osiz = cnf.oligosize.get()

        dseq = dict(sequences.read(path)) if Path(path).exists() else {}
        if len(dseq) == 0:
            return dict(values = [0], inds = [0], text = [''])

        nbases = max(len(i) for i in dseq.values())
        data   = dict(values = np.arange(nbases),
                      inds   = np.full((nbases,), 0.5, dtype = 'f4'))
        for name, seq in dseq.items():
            data[name] = np.full((nbases,), ' ', dtype = 'U%d' % osiz)
            data[name][:len(seq)-osiz+1] = [seq[i:i+osiz] for i in range(len(seq)-osiz+1)]

        data['text'] = data.get(key, data[next(iter(dseq))])
        return data

    def createhist(self, fig, cnf):
        u"Creates the hover tool for histograms"
        self.update(framerate = 1./30.,
                    bias      = 0.,
                    slope     = cnf.baseslope.get())

        hover = fig.select(HoverTool)
        if len(hover) == 0:
            return

        self._histsource = ColumnDataSource(self._createhistdata(cnf))
        hover[0].tooltips   = '@text'
        hover[0].mode       = 'hline'

        hover[0].renderers  = [fig.circle(x                = 'inds',
                                          y                = 'values',
                                          source           = self._histsource,
                                          radius           = 1,
                                          radius_dimension = 'y',
                                          line_alpha       = 0.,
                                          fill_alpha       = 0.,
                                          x_range_name     = 'cycles',
                                          y_range_name     = 'bases',
                                          visible          = False)]

    def updateraw(self, fig, rdata):
        u"updates the tooltips for a new file"
        hover = fig.select(HoverTool)
        if len(hover) == 0:
            return

        self._rawsource.data  = self._createrawdata(rdata)

    def updatehist(self, fig, track, hdata, cnf):
        u"updates the tooltips for a new file"
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

class _CyclesPlotterMixin:
    if TYPE_CHECKING:
        def getConfig(self):
            u"returns the config"
            raise NotImplementedError()
        def key(self):
            u"returns the plot key"
            raise NotImplementedError()
        def _figargs(self, cnf, width, loc):
            u"returns figure args"
            raise NotImplementedError()

class _CyclesRawPlotterMixin(_CyclesPlotterMixin): # pylint: disable=abstract-method
    def __init__(self,  ctrl:Controller) -> None:
        "sets up this plotter's info"
        cnf = ctrl.getGlobal(self.key())
        cnf.defaults = dict(raw = PlotAttrs('blue',  'circle', 1,
                                            alpha   = .5,
                                            palette = 'inferno'))

        self._rawsource  = ColumnDataSource()
        self._raw        = figure(y_axis_label = self.getConfig().ylabel.get(),
                                  y_range      = Range1d(start = 0., end = 1.),
                                  **self._figargs(cnf, 500, 'left'))

    @_checksizes
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
        raw             = self._createrawdata(track, bead)
        self._rawsource = ColumnDataSource(data = raw)

        cnf             = self.getConfig()
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

class _CyclesHistPlotterMixin(_CyclesPlotterMixin): # pylint: disable=abstract-method
    def __init__(self,  ctrl:Controller, yrng) -> None:
        "sets up this plotter's info"
        cnf = ctrl.getGlobal(self.key())
        cnf.defaults = dict(binwidth  = .003,
                            minframes = 10,
                            basebias  = None,
                            baseslope = 8.8e-4,
                            frames    = PlotAttrs('white', 'quad',   1,
                                                  line_color = 'gray',
                                                  fill_color = 'gray'),
                            cycles    = PlotAttrs('white', 'quad',   1,
                                                  fill_alpha = 0.,
                                                  line_color = 'blue'),
                           )
        cnf.hist.defaults = dict(xtoplabel = u'Cycles',
                                 xlabel    = u'Frames',
                                 ylabel    = u'Base number')

        self._histsource = ColumnDataSource()
        self._hist       = figure(y_axis_location = None,
                                  y_range         = yrng,
                                  **self._figargs(cnf.hist, 200, None))

    @_checksizes
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
        # pylint: disable=protected-access,no-member,too-many-arguments
        def _onchangebounds(yrng   = self._hist.y_range,
                            frames = self._hist.x_range,
                            cycles = self._hist.extra_x_ranges["cycles"],
                            bases  = self._hist.extra_y_ranges['bases'],
                            mdl    = self._hover,
                            src    = self._histsource):
            if yrng.bounds is not None:
                yrng._initial_start = yrng.bounds[0]
                yrng._initial_end   = yrng.bounds[1]

            counts = src.data["frames"]
            if len(counts) < 2:
                return
            bottom = src.data["bottom"]
            delta  = bottom[1]-bottom[0]

            ind1 = min(len(bottom), max(0, int((yrng.start-bottom[0])/delta-1)))
            ind2 = min(len(bottom), max(0, int((yrng.end  -bottom[0])/delta+1)))
            frames.start = 0.
            frames.end   = window.Math.max.apply(None, counts[ind1:ind2])+1

            counts = src.data["cycles"]
            cycles.start = 0.
            cycles.end   = window.Math.max.apply(None, counts[ind1:ind2])+1

            bases.start = (yrng.start-mdl.bias)/mdl.slope
            bases.end   = (yrng.end-mdl.bias)/mdl.slope

        self._hist.y_range.callback = CustomJS.from_py_func(_onchangebounds)

    def _createhist(self, track, bead):
        hist             = self._createhistdata(track, bead)
        self._histsource = ColumnDataSource(data = hist)

        self._hist.extra_x_ranges = {"cycles": Range1d(start = 0., end = 1.)}

        cnf   = self.getConfig()
        attrs = cnf.cycles.get()
        axis  = LinearAxis(x_range_name="cycles", axis_label = cnf.hist.xtoplabel.get())
        axis.axis_label_text_color = attrs.line_color
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

        self._hist.extra_y_ranges = {"bases": Range1d(start = 0., end = 1.)}
        axis = LinearAxis(y_range_name="bases", axis_label = cnf.hist.ylabel.get())
        self._hist.add_layout(axis, 'right')

        self._hover.createhist(self._hist, self.getConfig())
        self._slavexaxis()

    def _updatehist(self, track, bead):
        self._hist.disabled   = False
        self._histsource.data = hist = self._createhistdata(track, bead)
        self._hover.updatehist(self._hist, track, hist, self.getConfig())
        self.setbounds(self._hist.y_range, 'y', (hist['bottom'][0], hist['top'][-1]))

class CyclesPlotter(_TrackPlotter, _CyclesHistPlotterMixin, _CyclesRawPlotterMixin):
    "Displays cycles and their projection"
    def __init__(self,  ctrl:Controller) -> None:
        "sets up this plotter's info"
        _TrackPlotter.__init__(self, ctrl)

        cnf = ctrl.getGlobal(self.key())
        cnf.defaults = dict(tools     = 'ypan,ybox_zoom,reset,save,hover',
                            ncycles   = 150,
                            **DpxHoverModel.defaultconfig()
                           )
        self._hover      = DpxHoverModel()

        _CyclesRawPlotterMixin.__init__(self, ctrl)
        _CyclesHistPlotterMixin.__init__(self, ctrl, self._raw.y_range)

    def _figargs(self, cnf, width, loc): # pylint: disable=arguments-differ
        args = super()._figargs()
        args['x_axis_label']     = cnf.xlabel.get()
        args['plot_width']       = width
        args['toolbar_location'] = loc
        return args

    def _create(self, track, bead) -> DpxKeyedRow:
        u"returns the figure"
        self._createraw(track, bead)
        self._createhist(track, bead)
        row = gridplot([[self._raw, self._hist]])

        return DpxKeyedRow(self, self._raw,
                           children = [row],
                           toolbar  = row.children[0])

    def _update(self, track, bead):
        self._updateraw(track, bead)
        self._updatehist(track, bead)

class TrackPlot(BokehView):
    "Track plot view"
    PLOTTTER = BeadPlotter
    def __init__(self, **kwa):
        super().__init__(**kwa)
        self._plotter = self.PLOTTTER(self._ctrl)
        self._ctrl.observe("globals.current", self._onUpdateCurrent)

    def close(self):
        "remove controller"
        super().close()
        self._plotter.close()
        self._plotter = None

    def _onUpdateCurrent(self, **items):
        self._plotter.update(items) # pylint: disable=no-member

    def getroots(self):
        "adds items to doc"
        return self._plotter.create(),

class CyclesPlot(TrackPlot):
    "Track cycles plot view"
    PLOTTTER = CyclesPlotter
