#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Utils for dealing with the JS side of the view"
from bokeh.models           import Row
from bokeh.core.properties  import Dict, String, Float

from control                import Controller
from utils                  import coffee

class KeyedRow(Row):
    u"define div with tabIndex"
    keys               = Dict(String, String, help = u'keys and their action')
    zoomrate           = Float()
    panrate            = Float()
    __implementation__ = coffee(__file__, 'keyedrow')
    def __init__(self, plotter, **kwa):
        vals = ('.'.join((tool, axis, edge))
                for tool in ('pan', 'zoom')
                for axis in ('x', 'y')
                for edge in ('low', 'high'))

        cnf   = plotter.getConfig().keypress
        keys  = dict((cnf[key].get(), key) for key in vals)
        keys[cnf.reset.get()] = 'reset'
        keys.update({cnf[tool].activate.get(): tool for tool in ('pan', 'zoom')})

        kwa.setdefault('sizing_mode', 'stretch_both')
        super().__init__(children = [plotter.create()],
                         keys     = keys,
                         zoomrate = cnf.zoom.rate.get(),
                         panrate  = cnf.pan.rate.get(),
                         **kwa)

class PlotAttrs:
    u"Plot Attributes for one variable"
    def __init__(self, color = 'blue', glyph = 'line', size = 1):
        self.color = color
        self.glyph = glyph
        self.size  = size

    def addto(self, fig, **kwa):
        u"adds itself to plot: defines color, size and glyph to use"
        args  = dict(color  = self.color,
                     size   = self.size,
                     **kwa
                    )
        if self.glyph == 'line':
            args['line_width'] = args.pop('size')

        getattr(fig, self.glyph)(**args)

class Plotter:
    u"Base plotter class"
    def __init__(self, ctrl:Controller) -> None:
        u"sets up this plotter's info"
        ctrl.addGlobalMap(self.key())
        ctrl.addGlobalMap(self.key('current'))
        self._ctrl = ctrl

    @classmethod
    def key(cls, base = 'config'):
        u"Returns the key used by the global variables"
        return base+".plot."+cls.__name__[:-len('Plotter')].lower()

    def close(self):
        u"Removes the controller"
        del self._ctrl

    def getConfig(self):
        u"returns config values"
        return self._ctrl.getGlobal(self.key())

    def getCurrent(self, *key, **kwa):
        u"returns config values"
        return self._ctrl.getGlobal(self.key('current'), '.'.join(key), **kwa)

    def create(self):
        u"returns the figure"
        raise NotImplementedError("need to create")

    def _figargs(self):
        return dict(tools       = self.getConfig().tools.get(),
                    sizing_mode = 'stretch_both')

    def bounds(self, arr):
        u"Returns boundaries for a column"
        if len(arr) == 0:
            return 0., 1.

        vmin  = min(arr)
        vmax  = max(arr)
        delta = (vmax-vmin)*self.getConfig().boundary.overshoot.get()
        vmin -= delta
        vmax += delta
        return vmin, vmax

class SinglePlotter(Plotter):
    u"Base plotter class with single figure"
    def _addcallbacks(self, fig):
        u"adds Range callbacks"
        def _onchange(attr, old, new): # pylint: disable=unused-argument
            self._ctrl.updateGlobal(self.key('current'),
                                    x = (fig.x_range.start, fig.x_range.end),
                                    y = (fig.y_range.start, fig.y_range.end))

        fig.x_range.on_change('start', _onchange)
        fig.x_range.on_change('end',   _onchange)
        fig.y_range.on_change('start', _onchange)
        fig.y_range.on_change('end',   _onchange)
        return fig

    def create(self):
        u"returns the figure"
        fig = self._create()
        if fig is not None:
            self._addcallbacks(fig)
        return fig

    def _create(self):
        u"Specified by child class. Returns figure"
        raise NotImplementedError()
