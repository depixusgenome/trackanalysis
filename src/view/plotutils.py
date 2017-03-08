#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Utils for dealing with the JS side of the view"
from typing                 import Tuple, Optional, Iterator # pylint: disable =unused-import
from contextlib             import contextmanager
from itertools              import product

import bokeh.palettes
from bokeh.models           import Row, CustomJS, Range1d, Model
from bokeh.core.properties  import Dict, String, Float, Instance
from bokeh.plotting.figure  import Figure

from control                import Controller

class DpxKeyedRow(Row):
    u"define div with tabIndex"
    fig                = Instance(Figure)
    toolbar            = Instance(Model)
    keys               = Dict(String, String, help = u'keys and their action')
    zoomrate           = Float()
    panrate            = Float()
    __implementation__ = 'keyedrow.coffee'
    def __init__(self, plotter, fig, **kwa):
        vals = ('.'.join(i) for i in product(('pan', 'zoom'), ('x', 'y'), ('low', 'high')))
        cnf   = plotter.getConfig().keypress

        keys  = dict((cnf[key].get(), key) for key in vals)
        keys[cnf.reset.get()] = 'reset'
        keys.update({cnf[tool].activate.get(): tool for tool in ('pan', 'zoom')})

        kwa.setdefault('sizing_mode', 'stretch_both')
        children = kwa.pop('children', [fig])
        super().__init__(children = children,
                         fig      = fig,
                         keys     = keys,
                         zoomrate = cnf.zoom.rate.get(),
                         panrate  = cnf.pan.rate.get(),
                         **kwa)

class PlotAttrs:
    u"Plot Attributes for one variable"
    def __init__(self,
                 color                  = 'blue',
                 glyph                  = 'line',
                 size                   = 1,
                 palette: Optional[str] = None,
                 **kwa) -> None:
        self.color   = color
        self.glyph   = glyph
        self.size    = size
        self.palette = palette
        self.__dict__.update(kwa)

    def iterpalette(self, count, *tochange, indexes = None) -> Iterator['PlotAttrs']:
        u"yields PlotAttrs with colors along the palette provided"
        info    = dict(self.__dict__)
        palette = getattr(bokeh.palettes, self.palette, None)

        if palette is None:
            for _ in range(count):
                yield PlotAttrs(**info)
            return

        colors = palette(count)
        if indexes is not None:
            colors = [colors[i] for i in indexes]

        if len(tochange) == 0:
            tochange = ('color',)

        for color in colors:
            info.update((name, color) for name in tochange)
            yield PlotAttrs(**info)

    def addto(self, fig, **kwa):
        u"adds itself to plot: defines color, size and glyph to use"
        args  = dict(self.__dict__)
        args.pop('glyph')
        args.pop('palette')
        args.update(kwa)
        if self.glyph in ('line', 'quad'):
            args['line_width'] = args.pop('size')

        return getattr(fig, self.glyph)(**args)

class Plotter:
    u"Base plotter class"
    def __init__(self, ctrl:Controller) -> None:
        u"sets up this plotter's info"
        self._ctrl  = ctrl
        self._ready = False

        ctrl.addGlobalMap(self.key())
        ctrl.addGlobalMap(self.key('current'))
        self.getConfig().defaults = dict(ylabel    = u'Z',
                                         xtoplabel = u'Time',
                                         xlabel    = u'Frames')

    @contextmanager
    def updating(self):
        u"Stops on_change events for a time"
        self._ready = False
        yield self
        self._ready = True

    @staticmethod
    def fixreset(arng):
        u"Corrects the reset bug in bokeh"
        assert isinstance(arng, Range1d)
        def _onchangebounds(rng = arng):
            # pylint: disable=protected-access,no-member
            if rng.bounds is not None:
                rng._initial_start = rng.bounds[0]
                rng._initial_end   = rng.bounds[1]

        arng.callback = CustomJS.from_py_func(_onchangebounds)


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
        return dict(tools          = self.getConfig().tools.get(),
                    toolbar_sticky = False,
                    sizing_mode    = 'stretch_both',
                    disabled       = True)

    def newbounds(self, rng, axis, arr) -> dict:
        u"Sets the range boundaries"
        over  = self.getConfig().boundary.overshoot.get()

        vmin  = min(arr)
        vmax  = max(arr)
        delta = (vmax-vmin)*over*.5
        vmin -= delta
        vmax += delta

        if axis is None:
            curr  = None, None # type: Tuple[Optional[float], Optional[float]]
        else:
            curr  = self.getCurrent(axis, default = (vmin, vmax))

        attrs = dict(bounds        = (vmin, vmax),
                     start         = vmin if curr[0]  is None else curr[0],
                     end           = vmax if curr[1]  is None else curr[1],
                     range_padding = over*100.)
        if not hasattr(rng, 'range_padding'):
            attrs.pop('range_padding')

        return attrs

    def _addcallbacks(self, fig):
        u"adds Range callbacks"
        def _onchange(attr, old, new): # pylint: disable=unused-argument
            if self._ready:
                self._ctrl.updateGlobal(self.key('current'),
                                        x = (fig.x_range.start, fig.x_range.end),
                                        y = (fig.y_range.start, fig.y_range.end))

        fig.x_range.on_change('start', _onchange)
        fig.x_range.on_change('end',   _onchange)
        fig.y_range.on_change('start', _onchange)
        fig.y_range.on_change('end',   _onchange)
        return fig

    def setbounds(self, rng, axis, arr, reinit = True):
        u"Sets the range boundaries"
        if reinit and hasattr(rng, 'reinit'):
            rng.update(reinit = not rng.reinit, **self.newbounds(rng, axis, arr))
        else:
            rng.update(**self.newbounds(rng, axis, arr))

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
