#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"The basic architecture"
from copy   import deepcopy
from enum   import Enum
from typing import Tuple, Optional, Any

from utils  import initdefaults

RangeType  = Tuple[Optional[float], Optional[float]]

class PlotState(Enum):
    "plot state"
    active       = 'active'
    abouttoreset = 'abouttoreset'
    resetting    = 'resetting'
    disabled     = 'disabled'
    outofdate    = 'outofdate'

class PlotAttrs:
    "Plot Attributes for one variable"
    _GLYPHS = {
        '-' : 'line',    'o': 'circle', '△': 'triangle',
        '◇' : 'diamond', '□': 'square', '┸': 'quad',
        '+' : 'cross'
    }
    def __init__(self,
                 color   = '~blue',
                 glyph   = 'line',
                 size    = 1,
                 palette = None,
                 **kwa) -> None:
        self.color   = color
        self.glyph   = self._GLYPHS.get(glyph, glyph)
        self.size    = size
        self.palette = palette
        self.__dict__.update(kwa)
        for i in ('color', 'selection_color', 'nonselection_color'):
            color = self.__dict__.get(i, None)
            if isinstance(color, str) and len(color) and color[0] == '~':
                self.__dict__[i] = {'dark': f'light{color[1:]}', 'basic': f'dark{color[1:]}'}

def defaultfigsize(*args) -> Tuple[int, int, str]:
    "return the default fig size"
    return args+(700, 600, 'fixed')[len(args):] # type: ignore

class PlotTheme:
    """
    Default plot theme
    """
    name           = ''
    ylabel         = 'Z (μm)'
    yrightlabel    = 'Bases'
    xtoplabel      = 'Time (s)'
    xlabel         = 'Frames'
    figsize        = defaultfigsize()
    overshoot      = .001
    boundsovershoot= 1.
    output_backend = 'canvas'
    toolbar        = dict(sticky   = False,
                          location = 'above',
                          items    = 'xpan,box_zoom,wheel_zoom,save',
                          hide     = True)
    tooltips: Any  = None
    @initdefaults(frozenset(locals()))
    def __init__(self, **kwa):
        pass

    defaultfigsize = staticmethod(defaultfigsize)

class PlotDisplay:
    """
    Default plot display
    """
    name               = ""
    state              = PlotState.active
    __NONE             = (None, None)
    xinit:   RangeType = __NONE
    yinit:   RangeType = __NONE
    xbounds: RangeType = __NONE
    ybounds: RangeType = __NONE
    @initdefaults(frozenset(locals()))
    def __init__(self, **kwa):
        pass

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
