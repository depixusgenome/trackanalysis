#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Track plot view"

from bokeh.plotting import figure
from bokeh.models   import LinearAxis, Range1d, ColumnDataSource, CustomJS
from flexx          import app, event, ui

from control.event  import Controller # pylint: disable=unused-import
from .              import FlexxView

class BeadPlotter(app.Model):
    u"Plots a default bead"
    _KEY  = 'plot.bead.'
    _ctrl = None # type: Controller
    def observe(self, ctrl):
        u"sets up this plotter's info"
        ctrl.updateConfigDefault({
            self._KEY+"tools"      : 'xpan,wheel_zoom,box_zoom,undo,redo,reset,save',
            self._KEY+"z.color"    : 'blue',
            self._KEY+"z.glyph"    : 'circle',
            self._KEY+"z.size"     : 1,
            self._KEY+"zmag.color" : 'red',
            self._KEY+"zmag.glyph" : 'line',
            self._KEY+"zmag.size"  : 1,
            })
        self._ctrl = ctrl

    def get(self, *key, **kwa):
        u"returns config values"
        return self._ctrl.getConfig(self._KEY+'.'.join(key), **kwa)

    def _createdata(self, task):
        items = next(iter(self._ctrl.run(task, task)))
        bead  = self._ctrl.getGlobal("current.bead", default = None)
        if bead is None:
            bead = next(iter(items.keys()))

        data   = data=dict(t    = items['t'],
                           zmag = items['zmag'],
                           z    = items[bead])
        source = ColumnDataSource(data = data)
        return data, source

    def _figargs(self):
        args = dict(tools        = self.get("tools"),
                    x_axis_label = 'Time',
                    y_axis_label = 'z')

        for i in ('x', 'y'):
            rng  = self.get(i, default = None)
            if rng is not None:
                args[i+'_range'] = rng
        return args

    def _addglyph(self, source, beadname, fig, **kwa):
        glyph = self.get(beadname, "glyph")
        args  = dict(x      = 't',
                     y      = beadname,
                     source = source,
                     color  = self.get(beadname,"color"),
                     size   = self.get(beadname,"size"),
                     **kwa
                    )
        if glyph == 'line':
            args['line_width'] = args.pop('size')

        getattr(fig, glyph)(**args)

    @staticmethod
    def _addylayout(data, fig):
        vmin  = data['zmag'].min()
        vmax  = data['zmag'].max()
        delta = (vmax-vmin)*.02
        vmin -= delta
        vmax += delta

        fig.extra_y_ranges = {'zmag': Range1d(start = vmin, end = vmax)}
        fig.add_layout(LinearAxis(y_range_name='zmag'), 'right')

    def _addcallbacks(self, fig):
        rng = fig.extra_y_ranges['zmag']

        vstart, vend, vid = None, None, None
        def _onRangeChange(rng    = rng,
                           xrng   = fig.x_range,
                           yrng   = fig.y_range,
                           window = None):
            rng.start = vstart
            rng.end   = vend
            window.flexx.instances[vid].change(xrng.start, xrng.end,
                                               yrng.start, yrng.end)

        fcn      = CustomJS.from_py_func(_onRangeChange)
        fcn.code = (fcn.code
                    .replace('vstart', str(rng.start))
                    .replace('vend',   str(rng.end))
                    .replace('vid',    '"'+self.id+'"'))
        rng.callback = fcn


    def __call__(self):
        u"sets-up the figure"
        task = self._ctrl.getGlobal("current.track", default = None)
        if task is None:
            return figure(tools = [])

        data, source = self._createdata(task)

        fig = figure(**self._figargs())
        self._addylayout  (data, fig)
        self._addglyph    (source, "z",    fig)
        self._addglyph    (source, "zmag", fig, y_range_name = 'zmag')
        self._addcallbacks(fig)
        return fig

    @event.connect("change")
    def _on_change(self, *events):
        evt = events[-1]
        self._ctrl.updateGlobal({self._KEY+'x': (evt["xstart"], evt['xend']),
                                 self._KEY+'y': (evt["ystart"], evt['yend'])})

    class JS: # pylint: disable=missing-docstring,no-self-use
        @event.emitter
        def change(self, xstart, xend, ystart, yend):
            return dict(xstart = xstart, xend = xend,
                        ystart = ystart, yend = yend)

class TrackPlot(FlexxView):
    u"Track plot view"
    _plotter = None # type: BeadPlotter
    def init(self):
        ui.BokehWidget()
        self._plotter = BeadPlotter() # must change this to a Plot Factory

    def observe(self, ctrl):
        super().observe(ctrl)
        self._plotter.observe(ctrl)

        children = self.children[0], self._plotter # pylint: disable=no-member
        def _onUpdateGlobal(**items):
            if 'current.track' in items or 'current.bead' in items:
                children[0].plot = children[1]()

        ctrl.observe(_onUpdateGlobal)
