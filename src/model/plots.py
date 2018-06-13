#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"The basic architecture"
from copy   import deepcopy
from enum   import Enum
from typing import Tuple, Optional, List, Any, Dict, cast

from utils  import initdefaults

RANGE_TYPE  = Tuple[Optional[float], Optional[float]]

class PlotState(Enum):
    "plot state"
    active       = 'active'
    abouttoreset = 'abouttoreset'
    resetting    = 'resetting'
    disabled     = 'disabled'
    outofdate    = 'outofdate'

class PlotAttrs:
    "Plot Attributes for one variable"
    def __init__(self,
                 color        = 'blue',
                 glyph        = 'line',
                 size         = 1,
                 palette: str = None,
                 **kwa) -> None:
        self.color   = color
        self.glyph   = glyph
        self.size    = size
        self.palette = palette
        self.__dict__.update(kwa)

class PlotTheme:
    """
    Default plot theme
    """
    name          = ''
    ylabel        = 'Z (μm)'
    yrightlabel   = 'Base number'
    xtoplabel     = 'Time (s)'
    xlabel        = 'Frames'
    figsize       = 800, 600, 'fixed'
    overshoot     =.001
    toolbar       = dict(sticky   = False,
                         location = 'above',
                         items    = 'xpan,wheel_zoom,box_zoom,save')
    tooltips: Any = None
    @initdefaults(frozenset(locals()))
    def __init__(self, **kwa):
        pass

    def figargs(self, **kwa) -> Dict[str, Any]:
        "create a figure"
        tips = kwa.pop('tooltips', self.tooltips)
        args = {'toolbar_sticky':   self.toolbar['sticky'],
                'toolbar_location': self.toolbar['location'],
                'tools':            self.toolbar['items'],
                'x_axis_label':     self.xlabel,
                'y_axis_label':     self.ylabel,
                'plot_width':       self.figsize[0],
                'plot_height':      self.figsize[1],
                'sizing_mode':      self.figsize[2]}
        args.update(kwa)

        tools:list = []
        if isinstance(args['tools'], str):
            tools = cast(str, args['tools']).split(',')
        elif not args['tools']:
            tools = []
        else:
            tools = cast(List[Any], args['tools'])

        from view.plots.bokehext import DpxHoverTool
        if 'dpxhover' in tools:
            hvr   = DpxHoverTool(tooltips = tips) if tips else DpxHoverTool()
            tools = [i if i != 'dpxhover' else hvr for i in tools]

        args['tools'] = tools

        from bokeh.models import Range1d
        for name in ('x_range', 'y_range'):
            if args.get(name, None) is Range1d:
                args[name] = Range1d(start = 0., end = 1.)
        return args

    def figure(self, **kwa) -> 'Figure':
        "creates a figure"
        from bokeh.plotting import figure
        return figure(**self.figargs(**kwa))

class PlotDisplay:
    """
    Default plot display
    """
    name                = ""
    state               = PlotState.active
    xbounds: RANGE_TYPE = (None, None)
    ybounds: RANGE_TYPE = (None, None)
    @initdefaults(frozenset(locals()))
    def __init__(self, **kwa):
        pass

    def addcallbacks(self, ctrl, fig):
        "adds Range callbacks"
        updating = [False]
        def _get(axname):
            axis = getattr(fig, axname+'_range')

            def _on_cb(attr, old, new):
                if self.state is PlotState.active:
                    vals = cast(Tuple[Optional[float],...], (axis.start, axis.end))
                    if axis.bounds is not None:
                        rng  = 1e-3*(axis.bounds[1]-axis.bounds[0])
                        vals = tuple(None if abs(i-j) < rng else j
                                     for i, j in zip(axis.bounds, vals))
                    updating[0] = True
                    ctrl.display.update(self, **{axname+'bounds': vals})
                    updating[0] = False

            axis.on_change('start', _on_cb)
            axis.on_change('end',   _on_cb)

        _get('x')
        _get('y')

        def _onobserve(old = None, **_):
            if updating[0]:
                return
            for i in {'xbounds', 'ybounds'} & frozenset(old):
                rng  = getattr(fig, i[0]+'_range')
                vals = getattr(self, i)
                bnds = rng.bounds
                rng.update(start = bnds[0] if vals[0] is None else vals[0],
                           end   = bnds[1] if vals[1] is None else vals[1])
        ctrl.display.observe(self, _onobserve)
        return fig

class PlotModel:
    """
    base plot model
    """
    theme       = PlotTheme()
    display     = PlotDisplay()
    config: Any = None
    def __init__(self):
        self.theme   = deepcopy(self.theme)
        self.display = deepcopy(self.display)
        self.config  = deepcopy(self.config)
        assert self.theme.name
        assert self.display.name
        if self.config is not None:
            assert self.config.name, self
            assert self.config.name != self.theme.name, self

    def addto(self, ctrl, noerase = True):
        "sets-up model observers"
        self.theme   = ctrl.theme  .add(self.theme, noerase)
        self.display = ctrl.display.add(self.display, noerase)
        if self.config:
            self.config = ctrl.theme  .add(self.config, noerase)

    def observe(self, ctrl, noerase = False):
        "sets-up model observers"
        self.addto(ctrl, noerase)

    @classmethod
    def create(cls, ctrl, noerase = True):
        "creates the model and registers it"
        self = cls()
        self.addto(ctrl, noerase = noerase)
        return self
