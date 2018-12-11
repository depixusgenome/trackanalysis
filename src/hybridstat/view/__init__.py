#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"all view aspects here"
from collections         import OrderedDict
from typing              import Dict

from bokeh               import layouts
from bokeh.models        import Panel, Spacer, Tabs

from cleaning.view       import CleaningView
from cyclesplot          import CyclesPlotView
from fov                 import FoVPlotView
from model.plots         import PlotState
from qualitycontrol.view import QualityControlView
from utils               import dataclass
from view.base           import BokehView
from view.tabs           import TabsView, TabsTheme, initsubclass

from ._io                import setupio
from .peaksplot          import PeaksPlotView
from .cyclehistplot      import CycleHistPlotView
from .hairpingroup       import HairpinGroupPlotView

PANELS = {FoVPlotView          : 'fov',
          QualityControlView   : 'qc',
          CleaningView         : 'cleaning',
          CyclesPlotView       : 'cycles',
          PeaksPlotView        : 'peaks',
          CycleHistPlotView    : 'cyclehist',
          HairpinGroupPlotView : 'hairpin'}

NAME   = "CyclesApp"
class HybridStatTheme(TabsTheme):
    "HybridStatTheme"
    def __init__(self):
        super().__init__("cleaning", PANELS)

@initsubclass("HybridStat:Tabs", PANELS, (CleaningView, PeaksPlotView))
class HybridStatView(TabsView[HybridStatTheme]):
    "A view with all plots"
    APPNAME = "CycleApp"
