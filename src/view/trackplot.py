#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Track plot view"

from typing         import Optional  # pylint: disable=unused-import
from bokeh.plotting import figure
from bokeh.models   import (LinearAxis, Range1d, ColumnDataSource, HoverTool,
                            CustomJS)
import numpy

from control        import Controller
from .jsutils       import SinglePlotter, PlotAttrs
from .              import BokehView

class BeadPlotter(SinglePlotter):
    u"Plots a default bead"
    def __init__(self,  ctrl:Controller) -> None:
        u"sets up this plotter's info"
        super().__init__(ctrl)
        self._source = ColumnDataSource()
        self._fig    = figure(sizing_mode = 'stretch_both')
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
            arr = numpy.array([], dtype = numpy.float)
            return dict.fromkeys(('t', 'zmag', 'z'), arr)

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

    def _addglyph(self, beadname, **kwa):
        self.getConfig(beadname).addto(self._fig,
                                       x      = 't',
                                       y      = beadname,
                                       source = self._source,
                                       **kwa)

    def _bounds(self, name:str):
        arr   = self._get(name)
        if len(arr) == 0:
            return 0., 1.

        vmin  = min(arr)
        vmax  = max(arr)
        delta = (vmax-vmin)*.005
        vmin -= delta
        vmax += delta
        return vmin, vmax

    def _addylayout(self):
        vmin, vmax = self._bounds('zmag')
        self._fig.extra_y_ranges = {'zmag': Range1d(start = vmin, end = vmax)}
        self._fig.add_layout(LinearAxis(y_range_name='zmag', axis_label = u'zmag'), 'right')

    def _addcallbacks(self, fig):
        super()._addcallbacks(fig)
        rng   = self._fig.extra_y_ranges['zmag']
        def _onRangeChange(rng = rng):
            rng.start = rng.bounds[0]
            rng.end   = rng.bounds[1]

        rng.callback = CustomJS.from_py_func(_onRangeChange)

    def _setbounds(self):
        self._fig.x_range.bounds = self._bounds('t')
        self._fig.y_range.bounds = self._bounds('z')

        bnds = self._bounds("zmag")
        self._fig.extra_y_ranges['zmag'].bounds = bnds
        self._fig.extra_y_ranges['zmag'].start  = bnds[0]
        self._fig.extra_y_ranges['zmag'].end    = bnds[1]

    def _create(self):
        u"sets-up the figure"
        self._source = ColumnDataSource(data = self._createdata())
        self._fig.add_tools(HoverTool(tooltips = self.getConfig("tooltip")))

        self._addylayout  ()
        self._addglyph    ("z")
        self._addglyph    ("zmag", y_range_name = 'zmag')
        return self._fig

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
        self._source.stream(self._createdata(name), rollover = 1)
        self._setbounds()

class TrackPlot(BokehView):
    u"Track plot view"
    def __init__(self, **kwa):
        super().__init__(**kwa)
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
