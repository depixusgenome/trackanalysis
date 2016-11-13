#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Track plot view"

from bokeh.plotting import figure, Figure # pylint: disable=unused-import
from bokeh.models   import LinearAxis, Range1d, ColumnDataSource, HoverTool
from flexx.pyscript import window
from flexx          import event, ui

from control        import Controller
from .jsutils       import SinglePlotter, PlotAttrs
from .              import FlexxView

class BeadPlotter(SinglePlotter):
    u"Plots a default bead"
    def observe(self,  ctrl:Controller):
        u"sets up this plotter's info"
        super().observe(ctrl)
        ctrl.setGlobalDefaults(self.key(),
                               z       = PlotAttrs('blue', 'circle', 1),
                               zmag    = PlotAttrs('red',  'line',   1),
                               tooltip = [(u'Index',  '$index'),
                                          (u'(t, z, zmag)', '($x, @z, @zmag)')]
                              )

    def _createdata(self, task):
        items = next(iter(self._ctrl.run(task, task)))
        bead  = self._ctrl.getGlobal("current", "bead", default = None)
        if bead is None:
            bead = next(iter(items.keys()))

        data   = data = dict(t    = items['t'],
                             zmag = items['zmag'],
                             z    = items[bead])
        source = ColumnDataSource(data = data)
        return data, source

    def _figargs(self):
        args = dict(tools        = self.getConfig("tools"),
                    x_axis_label = u'Time',
                    y_axis_label = u'z')

        for i in ('x', 'y'):
            rng  = self.getCurrent(i, default = None)
            if rng is not None:
                args[i+'_range'] = rng
        return args

    def _addglyph(self, source, beadname, fig, **kwa):
        self.getConfig(beadname).addto(fig, x = 't', y = beadname, source = source, **kwa)

    @staticmethod
    def _bounds(arr):
        vmin  = arr.min()
        vmax  = arr.max()
        delta = (vmax-vmin)*.005
        vmin -= delta
        vmax += delta
        return vmin, vmax

    @classmethod
    def _addylayout(cls, data, fig):
        vmin, vmax = cls._bounds(data['zmag'])
        fig.extra_y_ranges = {'zmag': Range1d(start = vmin, end = vmax)}
        fig.add_layout(LinearAxis(y_range_name='zmag', axis_label = u'zmag'), 'right')

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

        rng.callback = self.callbackCode(_onRangeChange)

    def create(self):
        u"sets-up the figure"
        task = self._ctrl.getGlobal("current", "track", default = None)
        if task is None:
            return figure(tools = [])

        data, source = self._createdata(task)

        fig = figure(**self._figargs())
        fig.x_range.bounds = self._bounds(data['t'])
        fig.y_range.bounds = self._bounds(data['z'])
        fig.add_tools(HoverTool(tooltips = self.getConfig("tooltip")))

        self._addylayout  (data, fig)
        self._addglyph    (source, "z",    fig)
        self._addglyph    (source, "zmag", fig, y_range_name = 'zmag')

        self._addcallbacks(fig)

        return fig, self.keyargs()

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
    def _plotted(self, plotter, args):              # pylint: disable=no-self-use
        args['class'] = plotter.__class__.__name__
        return args

    def observe(self, ctrl):
        super().observe(ctrl)
        self._plotter.observe(ctrl)

        children = self.children[0], self._plotter  # pylint: disable=no-member
        def _onUpdateCurrent(**items):
            if 'track' in items or 'bead' in items:
                children[0].plot, args = children[1].create()
                self._plotted(children[1], args)

        ctrl.observe(_onUpdateCurrent)

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
