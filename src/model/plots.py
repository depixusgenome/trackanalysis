#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"The basic architecture"
from copy   import deepcopy
from enum   import Enum
from typing import Tuple, Optional, Any, cast

from utils  import initdefaults

RANGE_TYPE  = Tuple[Optional[float], Optional[float]] # pylint: disable=invalid-name

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
                 color   = 'blue',
                 glyph   = 'line',
                 size    = 1,
                 palette = None,
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
    figsize       = 700, 600, 'fixed'
    overshoot     =.001
    toolbar       = dict(sticky   = False,
                         location = 'above',
                         items    = 'xpan,wheel_zoom,box_zoom,save',
                         hide     = True)
    tooltips: Any = None
    @initdefaults(frozenset(locals()))
    def __init__(self, **kwa):
        pass

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
                if self.state in (PlotState.active, PlotState.resetting):
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

    def isactive(self) -> bool:
        "whether the plot is active"
        return self.state == PlotState.active

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
