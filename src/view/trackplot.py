#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Track plot view"

from bokeh.plotting import figure, Figure # pylint: disable=unused-import
from bokeh.models   import LinearAxis, Range1d, ColumnDataSource, CustomJS
from flexx          import app, event, ui, pyscript
from flexx.pyscript import window

from control        import Controller
from .              import FlexxView

class BeadPlotter(app.Model):
    u"Plots a default bead"
    _KEY    = 'plot.bead.'
    _ctrl   = None # type: Controller
    def unobserve(self):
        u"Removes the controller"
        del self._ctrl

    def observe(self,  ctrl:Controller):
        u"sets up this plotter's info"
        ctrl.updateConfigDefault({
            self._KEY+"tools"      : 'xpan,wheel_zoom,box_zoom,undo,redo,reset,save',
            self._KEY+"z.color"    : 'blue',
            self._KEY+"z.glyph"    : 'circle',
            self._KEY+"z.size"     : 1,
            self._KEY+"zmag.color" : 'red',
            self._KEY+"zmag.glyph" : 'line',
            self._KEY+"zmag.size"  : 1,
            'panning.speed'        : .2,
            'zooming.speed'        : .2,
            'keypress.pan.left'    : 'Left',
            'keypress.pan.right'   : 'Rigth',
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

    @staticmethod
    def _jscode(pyfcn):
        string = pyscript.py2js(pyfcn)
        for name, val in pyfcn.__closure__[0].cell_contents.items():
            string = string.replace('jsobj["%s"]' % name, str(val))
        return string

    @staticmethod
    def _callback(pyfcn):
        fcn = CustomJS.from_py_func(pyfcn)
        for name, val in pyfcn.__closure__[0].cell_contents.items():
            fcn.code = fcn.code.replace('jsobj["%s"]' % name, str(val))
        return fcn

    def _addcallbacks(self, fig):
        rng   = fig.extra_y_ranges['zmag']
        jsobj = dict(start = rng.start,
                     end   = rng.end,
                     key   = '"'+self.id+'"')
        def _onRangeChange(fig    = fig,
                           rng    = rng):
            rng.start = jsobj['start']
            rng.end   = jsobj['end']
            xrng      = fig.x_range
            yrng      = fig.y_range

            # pylint: disable=no-member
            window.flexx.instances[jsobj['key']].change(xrng.start, xrng.end,
                                                        yrng.start, yrng.end)

        rng.callback = self._callback(_onRangeChange)

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

        return fig, dict(pan  = self._ctrl.getConfig("panning.speed"),
                         zoom = self._ctrl.getConfig("zooming.speed"))

    @event.connect("change")
    def _on_change(self, *events):
        evt          = events[-1]
        xstart, xend = evt["xstart"], evt['xend']
        ystart, yend = evt["ystart"], evt['yend']
        self._ctrl.updateGlobal({self._KEY+'x': (xstart, xend),
                                 self._KEY+'y': (ystart, yend)})

    class JS: # pylint: disable=missing-docstring,no-self-use
        @event.emitter
        def change(self, xstart, xend, ystart, yend):
            return dict(xstart = xstart, xend = xend,
                        ystart = ystart, yend = yend)

        def onkeydown(self, fig, jsobj, evt):
            if evt.shiftKey:
                rng = fig.y_range
            else:
                rng = fig.x_range

            delta = (rng.end-rng.start)*jsobj['pan']
            if evt.keyCode == 37:
                rng.start = rng.start - delta
                rng.end   = rng.end   - delta

            elif evt.keyCode == 38:
                rng.start = rng.start + delta
                rng.end   = rng.end   - delta

            elif evt.keyCode == 39:
                rng.start = rng.start + delta
                rng.end   = rng.end   + delta

            elif evt.keyCode == 40:
                rng.start = rng.start - delta
                rng.end   = rng.end   + delta

            else:
                return

            fig.trigger("change")

class TrackPlot(FlexxView):
    u"Track plot view"
    _plotter = None # type: BeadPlotter
    def init(self):
        ui.BokehWidget()
        self._plotter = BeadPlotter() # must change this to a Plot Factory

    def unobserve(self):
        super().unobserve()
        self._plotter.unobserve()
        del self._plotter

    @event.emitter
    def _plotted(self, plotter, args):                       # pylint: disable=no-self-use
        args['class'] = plotter.__class__.__name__
        return args

    def observe(self, ctrl):
        super().observe(ctrl)
        self._plotter.observe(ctrl)

        children = self.children[0], self._plotter  # pylint: disable=no-member
        def _onUpdateGlobal(**items):
            if 'current.track' in items or 'current.bead' in items:
                children[0].plot, args = children[1]()
                self._plotted(children[1], args)

        ctrl.observe(_onUpdateGlobal)

    class JS: # pylint: disable=no-member,missing-docstring
        @event.connect("_plotted")
        def __get_plot_div(self, *events):
            obj = events[-1]
            def _onkeypress(evt):
                fig = self.children[0].plot.model
                fcn = getattr(window.flexx.classes, obj['class'])
                fcn.prototype.onkeydown(fig, obj, evt)

            self.children[0].node.children[0].tabIndex  = 1
            self.children[0].node.children[0].onkeydown = _onkeypress
