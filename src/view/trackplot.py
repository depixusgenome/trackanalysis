#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Track plot view"

from typing         import Optional  # pylint: disable=unused-import
from bokeh.plotting import figure
from bokeh.models   import LinearAxis, Range1d, ColumnDataSource, HoverTool

from control        import Controller
from .jsutils       import SinglePlotter, PlotAttrs
from .              import BokehView

class BeadPlotter(SinglePlotter):
    u"Plots a default bead"
    def __init__(self,  ctrl:Controller) -> None:
        u"sets up this plotter's info"
        super().__init__(ctrl)
        self._source = ColumnDataSource()
        ctrl.setGlobalDefaults(self.key(),
                               z       = PlotAttrs('blue', 'circle', 1),
                               zmag    = PlotAttrs('red',  'line',   1),
                               tooltip = [(u'Index',  '$index'),
                                          (u'(t, z, zmag)', '($x, @z, @zmag)')]
                              )

    def _get(self, name):
        return self._source.data[name] # pylint: disable=unsubscriptable-object

    def _createdata(self, name = all):
        task = self._ctrl.getGlobal("current", "track", default = None)
        if task is None:
            return dict.fromkeys(('t', 'zmag', 'z'), [])

        items = next(iter(self._ctrl.run(task, task)))
        bead  = self._ctrl.getGlobal("current", "bead", default = None)
        if bead is None:
            bead = next(iter(items.keys()))

        if name == 'all':
            return dict(t    = items['t'],
                        zmag = items['zmag'],
                        z    = items[bead])
        elif name == 'z':
            return {'z': items[bead]}
        else:
            return {name: items[name]}

    def _figargs(self):
        args = dict(tools        = self.getConfig("tools"),
                    x_axis_label = u'Time',
                    y_axis_label = u'z',
                    sizing_mode  = 'scale_height')

        for i in ('x', 'y'):
            rng  = self.getCurrent(i, default = None)
            if rng is not None:
                args[i+'_range'] = rng
        return args

    def _addglyph(self, beadname, fig, **kwa):
        self.getConfig(beadname).addto(fig,
                                       x      = 't',
                                       y      = beadname,
                                       source = self._source,
                                       **kwa)

    def _bounds(self, name:str):
        arr   = self._get(name)
        vmin  = arr.min()
        vmax  = arr.max()
        delta = (vmax-vmin)*.005
        vmin -= delta
        vmax += delta
        return vmin, vmax

    def _addylayout(self, fig):
        vmin, vmax = self._bounds('zmag')
        fig.extra_y_ranges = {'zmag': Range1d(start = vmin, end = vmax)}
        fig.add_layout(LinearAxis(y_range_name='zmag', axis_label = u'zmag'), 'right')

    def _addcallbacks(self, fig):
        super()._addcallbacks(fig)
        rng   = fig.extra_y_ranges['zmag']
        jsobj = dict(start = rng.start,
                     end   = rng.end)
        def _onRangeChange(rng = rng):
            rng.start = jsobj['start']
            rng.end   = jsobj['end']

        rng.callback = self.callbackCode(_onRangeChange)

    def _create(self):
        u"sets-up the figure"
        self._source = ColumnDataSource(data = self._createdata())

        fig                = figure()
        fig.x_range.bounds = self._bounds('t')
        fig.y_range.bounds = self._bounds('z')
        fig.add_tools(HoverTool(tooltips = self.getConfig("tooltip")))

        self._addylayout  (fig)
        self._addglyph    ("z",    fig)
        self._addglyph    ("zmag", fig, y_range_name = 'zmag')
        return fig

    def update(self, items:dict):
        u"Updates the data"
        name = 'all'  # type: ignore
        if 'track' in items:
            pass
        elif 'bead' in items:
            name = 'z'
        else:
            return

        length = len(self._get('t'))
        if length == 0:
            length = None
        self._source.stream(self._createdata(name), rollover = length)

class TrackPlot(BokehView):
    u"Track plot view"
    def __init__(self, **kwa):
        super().__init__(self, **kwa)
        self._plotter = BeadPlotter(self._ctrl) # must change this to a Plot Factory
        self._ctrl.observe("globals.current", self._onUpdateCurrent)

    def close(self):
        u"remove controller"
        super().close()
        self._plotter.close()
        self._plotter = None

    def _onUpdateCurrent(self, **items):
        self._plotter.update(items)

    def getroots(self):
        u"adds items to doc"
        return self._plotter.create(),
