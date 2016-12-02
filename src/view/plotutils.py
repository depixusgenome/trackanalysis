#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Utils for dealing with the JS side of the view"
from typing                 import Dict, Optional, Union # pylint: disable=unused-import
from bokeh.models           import PanTool, BoxZoomTool
from bokeh.core.properties  import String, Float, HasProps

from control                import Controller

class ToolWithKeys(HasProps):
    u"Base class for controlling gestures with keyboard"
    @staticmethod
    def jscode(name, fname, meta) -> str:
        u"returns the javascript implementation code"
        return (u"""
        p     = require "core/properties"
        {name} = require "models/tools/gestures/{fname}"
        $      = require "jquery"

        class Dpx{name}View extends {name}.View
            _kdact: false
            _keytostr: (evt) ->
                val = ""
                cnv = alt: 'Alt', shift: 'Shift', ctrl: 'Control', meta: 'Meta'
                for name, kw of cnv
                    if evt[name+'Key']
                         val += "#{kw}-"

                val = if val == (evt.key+'-') then evt.key else val+evt.key

            _keydown: (evt) ->
                val = @_keytostr(evt)

                frame = @plot_view.frame
                isx   = val == @keyXLow or val == @keyXHigh
                e1    = {bokeh: {sx: 1, sy: if isx then 1 else frame.height*@rate+1}}
                e2    = {bokeh: {sx: if isx then frame.width*@rate+1 else 1, sy: 1}}

                islow = val == @keyXLow or val == @keyYLow
                @_pan_start(if islow then e1 else e2)
                @_pan_end(if islow then e2 else e1)

        class Dpx{name} extends {name}.Model
            default_view: Dpx{name}View
            type: 'Dpx{name}'
            @define {
                keyXLow:   [p.String, "{meta}ArrowLeft"],
                keyXHigh:  [p.String, "{meta}ArrowRight"],
                keyYLow:   [p.String, "{meta}ArrowDown"],
                keyYHigh:  [p.String, "{meta}ArrowUp"],
                rate:      [p.Float,  0.2]
            }

        module.exports =
            Model: Dpx{name}
            View:  Dpx{name}View
             """.replace('{name}',  name)
                .replace('{fname}', fname)
                .replace('{meta}',  meta))

    _KEY     = None # type: str
    keyXLow  = String()
    keyXHigh = String()
    keyYLow  = String()
    keyYHigh = String()
    rate     = Float ()

    @classmethod
    def fromconfig(cls, ctrl: 'Optional[Plotter]' = None, **kwa) \
            -> 'Dict[str,Union[str,float]]':
        u"returns dictionnary with attribute values extracted from the controller"
        items = dict()  # type: Dict[str,Union[str,float]]
        if ctrl is not None:
            key   = 'keypress.'+cls._KEY+'.'
            items = dict(keyXLow  = ctrl.getConfig(key+"x.low"),
                         keyXHigh = ctrl.getConfig(key+"x.high"),
                         keyYLow  = ctrl.getConfig(key+"y.low"),
                         keyYHigh = ctrl.getConfig(key+"y.high"),
                         rate     = ctrl.getConfig(key+"speed"))
        items.update(**kwa)
        return items

    def update(self, ctrl = None, **kwa):
        super().update(**self.fromconfig(ctrl, **kwa))

class DpxPanTool(PanTool, ToolWithKeys):        # pylint: disable=too-many-ancestors
    u"Adds keypress controls to the default PanTool"
    __implementation__ = ToolWithKeys.jscode('DpxPanTool', 'pan_tool', '')
    _KEY               = 'pan'
    def __init__(self, ctrl = None, **kwa):
        super().__init__(**self.fromconfig(ctrl, **kwa))

class DpxBoxZoomTool(BoxZoomTool, ToolWithKeys): # pylint: disable=too-many-ancestors
    u"Adds keypress controls to the default BoxZoomTool"
    __implementation__ = ToolWithKeys.jscode('DpxBoxZoomTool', 'box_zoom_tool', 'Shift')
    _KEY               = 'zoom'
    def __init__(self, ctrl = None, **kwa):
        super().__init__(**self.fromconfig(ctrl, **kwa))

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

    def getConfig(self, *key, **kwa):
        u"returns config values"
        return self._ctrl.getGlobal(self.key(), '.'.join(key), **kwa)

    def getCurrent(self, *key, **kwa):
        u"returns config values"
        return self._ctrl.getGlobal(self.key('current'), '.'.join(key), **kwa)

    def create(self):
        u"returns the figure"
        raise NotImplementedError("need to create")

    def _figargs(self):
        imp   = dict(pan  = lambda: DpxPanTool(self),
                     xpan = lambda: DpxPanTool(self, dimensions = 'width'),
                     ypan = lambda: DpxPanTool(self, dimensions = 'height'),
                     zoom = lambda: DpxBoxZoomTool(self))
        tools = [i if i.strip() not in imp else imp[i.strip()]()
                 for i in self.getConfig("tools").split(',')]
        return dict(tools = tools, sizing_mode = 'scale_height')

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

    class JS: # pylint: disable=missing-docstring,no-self-use
        def _dozoom(self, jsobj, found, rng):
            center = (rng.end+rng.start)*.5
            delta  = (rng.end-rng.start)
            if found.endswith('.in'):
                delta  *= jsobj['zoom']
            else:
                delta  /= jsobj['zoom']

            rng.start = center - delta*.5
            if rng.start < rng.bounds[0]:
                rng.start = rng.bounds[0]

            rng.end   = center + delta*.5
            if rng.end > rng.bounds[1]:
                rng.end   = rng.bounds[1]

        def _dopan(self, jsobj, found, rng):
            delta = (rng.end-rng.start)*jsobj['pan']
            if found.endswith('.low'):
                delta *= -1.

            rng.start = rng.start + delta
            rng.end   = rng.end   + delta
            if rng.start < rng.bounds[0]:
                rng.end   = rng.bounds[0] + rng.end-rng.start
                rng.start = rng.bounds[0]
            elif rng.end > rng.bounds[1]:
                rng.start = rng.bounds[1] + rng.start-rng.end
                rng.end   = rng.bounds[1]
