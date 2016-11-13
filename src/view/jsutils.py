#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Utils for dealing with the JS side of the view"
from flexx          import pyscript, app, event
from bokeh.models   import CustomJS

from control        import Controller

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

class Plotter(app.Model):
    u"Base plotter class"
    _ctrl   = None # type: Controller

    @staticmethod
    def jsCode(pyfcn, dictname = 'jsobj') -> str:
        u"""
        Produces JS code and replaces closure variables with their values.

        For example:

        > jsobj = dict(myjsparam = control.getGlobal("my.js.param"))
        > def myjsfunc(arg):
        >    arg.param = jsobj['myjsparam']

        will produce JS code where occurences of jsobj["myjsparam"] is replaced
        by the value stored in jsobj.
        """
        string = pyscript.py2js(pyfcn)
        for name, val in pyfcn.__closure__[0].cell_contents.items():
            string = string.replace(dictname+'["%s"]' % name, str(val))
            string = string.replace(dictname+"['%s']" % name, str(val))
        return string

    @staticmethod
    def callbackCode(pyfcn, dictname = 'jsobj') -> CustomJS:
        u"Returns a bokeh CustomJS processed as by function `jscode`"
        fcn = CustomJS.from_py_func(pyfcn)
        for name, val in pyfcn.__closure__[0].cell_contents.items():
            fcn.code = fcn.code.replace(dictname+'["%s"]' % name, str(val))
            fcn.code = fcn.code.replace(dictname+"['%s']" % name, str(val))
        return fcn

    @classmethod
    def key(cls, base = 'config'):
        u"Returns the key used by the global variables"
        return base+".plot."+cls.__name__[:-len('Plotter')].lower()

    def unobserve(self):
        u"Removes the controller"
        del self._ctrl

    def observe(self,  ctrl:Controller):
        u"sets up this plotter's info"
        ctrl.addGlobalMap(self.key())
        ctrl.addGlobalMap(self.key('current'))
        self._ctrl = ctrl

    def getConfig(self, *key, **kwa):
        u"returns config values"
        return self._ctrl.getGlobal(self.key(), '.'.join(key), **kwa)

    def getCurrent(self, *key, **kwa):
        u"returns config values"
        return self._ctrl.getGlobal(self.key('current'), '.'.join(key), **kwa)

    def create(self):
        u"returns the figure"
        raise NotImplementedError("need to create")

    class JS: # pylint: disable=missing-docstring,no-self-use
        def decodeKeyEvent(self, evt):
            u"Converting JS event to something more flexx-like"
            # https://developer.mozilla.org/en-US/docs/Web/API/KeyboardEvent
            # key: chrome 51, ff 23, ie 9
            # code: chrome ok, ff 32, ie no
            modifiers = '-'.join([_ for _ in ('Alt', 'Shift', 'Ctrl', 'Meta')
                                  if evt[_.lower()+'Key']])
            key = evt.key
            if not key and evt.code:  # Chrome < v51
                key = evt.code
                if key.startswith('Key'):
                    key = key[3:]
                    if 'Shift' not in modifiers:
                        key = key.lower()
                elif key.startswith('Digit'):
                    key = key[5:]
            # todo: handle Safari and older browsers via keyCode
            key = {'Esc': 'Escape', 'Del': 'Delete'}.get(key, key)  # IE

            if len(modifiers):
                return modifiers+'-'+key
            else:
                return key

class SinglePlotter(Plotter):
    u"Base plotter class with single figure"
    def keyargs(self):
        u"args to be passed to JS.onkeydown"
        vals = self._ctrl.getGlobal(self.key())
        return dict(pan   = vals.get("panning.speed"),
                    zoom  = vals.get("zooming.speed"),
                    reset = vals.get("keypress.reset"),
                    **{'keypress.'+axis+'.'+func: vals.get('keypress.'+axis+'.'+func)
                       for axis in ('x', 'y')
                       for func in ('pan.low', 'pan.high', 'zoom.in', 'zoom.out')})

    @event.connect("change")
    def _on_change(self, *events):
        evt   = events[-1]
        xvals = evt["xstart"], evt['xend']
        yvals = evt["ystart"], evt['yend']
        self._ctrl.updateGlobal(self.key('current'), x = xvals, y = yvals)

    def create(self):
        u"returns the figure"
        raise NotImplementedError("need to create")

    class JS: # pylint: disable=missing-docstring,no-self-use
        @event.emitter
        def change(self, xstart, xend, ystart, yend):
            return dict(xstart = xstart, xend = xend,
                        ystart = ystart, yend = yend)

        def _dozoom(self, jsobj, found, rng):
            delta = (rng.end-rng.start)*jsobj['zoom']
            if found.endswith('.in'):
                rng.start = rng.start - delta
                rng.end   = rng.end   + delta
            elif found.endswith('.out'):
                rng.start = rng.start + delta
                if rng.start > rng.bounds[0]:
                    rng.start = rng.bounds[0]

                rng.end   = rng.end   - delta
                if rng.end > rng.bounds[1]:
                    rng.end   = rng.bounds[1]

        def _dopan(self, jsobj, found, rng):
            delta = (rng.end-rng.start)*jsobj['pan']
            if found.endswith('.low'):
                rng.start = rng.start - delta
                rng.end   = rng.end   - delta
                if rng.start < rng.bounds[0]:
                    rng.end   = rng.bounds[0] + rng.end-rng.start
                    rng.start = rng.bounds[0]
            elif found.endswith('.high'):
                rng.start = rng.start + delta
                rng.end   = rng.end   + delta
                if rng.end > rng.bounds[1]:
                    rng.start = rng.bounds[1] + rng.start-rng.end
                    rng.end   = rng.bounds[1]

        def onkeydown(self, fig, jsobj, evt):
            found = None
            key   = self.decodeKeyEvent(evt) # pylint: disable=no-member
            for name, val in jsobj.items():
                if key == val:
                    found = name
                    break

            if found is None:
                return

            if found == 'reset':
                fig.x_range.start = fig.x_range.bounds[0]
                fig.x_range.end   = fig.x_range.bounds[1]
                fig.y_range.start = fig.y_range.bounds[0]
                fig.y_range.end   = fig.y_range.bounds[1]
                return

            rng = getattr(fig, found[9]+'_range')
            if "zoom" in found:
                self._dozoom(jsobj, found, rng)
            elif "pan" in found:
                self._dopan(jsobj, found, rng)

            fig.trigger("change")
