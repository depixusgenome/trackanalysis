#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Track plot view"

from typing         import Optional  # pylint: disable=unused-import
from bokeh.model    import Model
from bokeh.core.properties  import Float
from bokeh.plotting import figure
from bokeh.layouts  import gridplot
from bokeh.models   import (LinearAxis, ColumnDataSource, HoverTool,
                            CustomJS, Range1d)

import numpy        as np
from control        import Controller
from .plotutils     import SinglePlotter, PlotAttrs, Plotter, DpxKeyedRow
from .              import BokehView

window = None # type: ignore # pylint: disable=invalid-name

class _PlotterMixin(type):
    _row = None # type: Optional[DpxKeyedRow]
    def __new__(mcs, clsname, bases, nspace, **_):
        # pylint: disable=protected-access
        assert len(bases) == 1
        plotter = bases[0]

        _old_init = nspace.pop('__init__')
        def __init__(self, *_):
            self._row = None # type: Optional[DpxKeyedRow]
            _old_init(self, *_)
        nspace['__init__'] = __init__

        _old_create = nspace.pop('create', None)
        if _old_create is None:
            _old_create = plotter.create
        def create(self) -> DpxKeyedRow:
            u"returns the figure"
            self._row = _old_create(self) # type: ignore
            self._row.disabled = True
            return self._row
        nspace['create'] = create

        def update(self, items:dict):
            "Updates the data"
            if not ('track' in items or 'bead' in items):
                return

            with self.updating():               # type: ignore
                self._row.disabled = False
                self._update()
        nspace['update'] = update

        if '_update' not in nspace:
            def _update(_):
                raise NotImplementedError()
            nspace['_update'] = _update

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
        nspace['_gettrack'] = _gettrack

        return type(clsname, (plotter,), nspace)

class BeadPlotter(SinglePlotter, metaclass = _PlotterMixin):
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
                                        (u'(t, z, zmag)', '($x, @z, @zmag)')])

    def _get(self, name):
        return self._source.data[name] # pylint: disable=unsubscriptable-object

    def _createdata(self):
        track, bead = self._gettrack() # pylint: disable=no-member
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
        args.update(x_axis_label = u'Time',
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

    def _create(self):
        "sets-up the figure"
        self._source = ColumnDataSource(data = self._createdata())
        if self.getConfig().tooltips.get() not in ('', None):
            self._fig.select(HoverTool).tooltips = self.getConfig().tooltips.get()

        self._addylayout  ()
        self._addglyph    ("zmag", y_range_name = 'zmag')

        self._addglyph    ("z")
        for rng in self._fig.x_range, self._fig.y_range, self._fig.extra_y_ranges['zmag']:
            self.fixreset(rng)
        return self._fig

    def _update(self):
        self._fig.disabled = False
        self._source.data  = self._createdata()
        self._setbounds()

class DpxHoverModel(Model):
    u"controls keypress actions"
    precision = Float(0.003)
    __implementation__ = """
    import * as p  from "core/properties"
    import {Model} from "model"

    export class DpxHoverModelView
    export class DpxHoverModel extends Model
        default_view: DpxHoverModelView
        type:"DpxHoverModel"
        @define { precision : [p.Number,  0.003] }
    """
    @staticmethod
    def defaultconfig() -> dict:
        u"default config"
        return dict(selraw  = PlotAttrs('green', 'line',   2))

    def tool(self, fig, source, cnf):
        u"creates the hover tool"
        self.precision = cnf['binwidth'].get()
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

        hover = fig.select(HoverTool)
        hover.tooltips = None
        hover.callback = CustomJS.from_py_func(_onhover)

class CyclesPlotter(Plotter, metaclass = _PlotterMixin):
    "Displays cycles and their projection"
    def __init__(self,  ctrl:Controller) -> None:
        "sets up this plotter's info"
        super().__init__(ctrl)
        cnf = ctrl.getGlobal(self.key())
        cnf.defaults = dict(binwidth  = .003,
                            tools     = 'ypan,ybox_zoom,reset,save',
                            ncycles   = 150,
                            minframes = 10,
                            raw       = PlotAttrs('blue',  'circle', 1,
                                                  alpha   = .5,
                                                  palette = 'inferno'),
                            frames    = PlotAttrs('white', 'quad',   1,
                                                  line_color = 'gray',
                                                  fill_color = 'gray'),
                            cycles    = PlotAttrs('white', 'quad',   1,
                                                  fill_alpha = 0.,
                                                  line_color = 'blue'),
                            **DpxHoverModel.defaultconfig()
                           )

        self._rawsource  = ColumnDataSource()
        self._raw        = figure(y_axis_label = u'z',
                                  y_range      = Range1d(start = 0., end = 1.),
                                  **self._figargs(u'Time', 500, 'left','hover'))

        self._histsource = ColumnDataSource()
        self._hist       = figure(y_axis_location = None,
                                  y_range         = self._raw.y_range,
                                  **self._figargs(u'Frames', 200, None))

    def _figargs(self, # pylint: disable=arguments-differ
                 xaxis, width, loc, tools = None):
        args = super()._figargs()
        args['x_axis_label']     = xaxis
        args['plot_width']       = width
        args['toolbar_location'] = loc
        if tools is not None:
            args['tools'] += ','+tools
        return args

    def _createrawdata(self) -> dict:
        track, bead = self._gettrack() # pylint: disable=no-member
        keys        = set('C%d' % i for i in range(self.getConfig()['ncycles'].get()))
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

    def _createraw(self):
        raw             = self._createrawdata()
        attrs           = self.getConfig()['raw'].get()
        ncycles         = self.getConfig()['ncycles'].get()
        self._rawsource = ColumnDataSource(data = raw)
        for ind, attrs in enumerate(attrs.iterpalette(ncycles)):
            attrs.addto(self._raw,
                        x       = 't',
                        y       = 'C%d' % ind,
                        source  = self._rawsource,
                        tags    = ['__lines__'],
                        visible = raw['t'] is not raw['C%d' % ind])

        DpxHoverModel().tool(self._raw, self._rawsource, self.getConfig())

        fig = self._raw
        def _onchange(attr, old, new): # pylint: disable=unused-argument
            if self._ready:
                self._ctrl.updateGlobal(self.key('current'),
                                        x = (fig.x_range.start, fig.x_range.end),
                                        y = (fig.y_range.start, fig.y_range.end))

        fig.x_range.on_change('start', _onchange)
        fig.x_range.on_change('end',   _onchange)
        fig.y_range.on_change('start', _onchange)
        fig.y_range.on_change('end',   _onchange)

    def _createhistdata(self):
        track, bead   = self._gettrack() # pylint: disable=no-member
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
        def _onchangebounds(yrng   = self._hist.y_range,
                            frames = self._hist.x_range,
                            cycles = self._hist.extra_x_ranges["cycles"],
                            src    = self._histsource):
            # pylint: disable=protected-access,no-member
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

        self._hist.y_range.callback = CustomJS.from_py_func(_onchangebounds)

    def _createhist(self):
        hist             = self._createhistdata()
        self._histsource = ColumnDataSource(data = hist)

        self._hist.extra_x_ranges = {"cycles": Range1d(start = 0., end = 1.)}

        attrs = self.getConfig()['cycles'].get()
        axis  = LinearAxis(x_range_name="cycles", axis_label = u'Cycles')
        axis.axis_label_text_color = attrs.line_color
        self._hist.add_layout(axis, 'above')

        self.getConfig()['frames'].addto(self._hist,
                                         source = self._histsource,
                                         bottom = "bottom", top   = "top",
                                         left   = "left",   right = "frames")

        attrs.addto(self._hist,
                    source = self._histsource,
                    bottom = "bottom", top   = "top",
                    left   = "left",   right = "cycles",
                    x_range_name = "cycles")

        self._slavexaxis()

    def create(self) -> DpxKeyedRow:
        u"returns the figure"
        self._createraw()
        self._createhist()
        row = gridplot([[self._raw, self._hist]])

        return DpxKeyedRow(self, self._raw,
                           children = [row],
                           toolbar  = row.children[0])

    def _update(self):
        self._hist.disabled   = False
        self._raw.disabled    = False

        raw                   = self._createrawdata()
        self._rawsource.data  = raw
        for glyph in self._raw.select(tags = '__lines__'):
            glyph.visible = raw[glyph.y] is not raw['t']

        hist                  = self._createhistdata()
        self._histsource.data = hist
        self.setbounds(self._raw.y_range, None, (hist['bottom'][0], hist['top'][-1]))

        bnd = 0, np.max(hist['frames'])+1
        self._hist.x_range.update(bounds = bnd, start = 0, end = bnd[1])

        bnd = 0, np.max(hist["cycles"])+1
        self._hist.extra_x_ranges["cycles"].update(bounds = bnd,
                                                   start  = 0,
                                                   end    = bnd[1])

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
