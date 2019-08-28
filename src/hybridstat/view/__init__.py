#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"all view aspects here"
from cleaning.view       import CleaningView, BeadCleaningView
from cyclesplot          import CyclesPlotView
from fov                 import FoVPlotView
from qualitycontrol.view import QualityControlView
from taskview.tabs       import TabsView, TabsTheme, initsubclass

from .peaksplot          import PeaksPlotView
from .cyclehistplot      import CycleHistPlotView
from .hairpingroup       import HairpinGroupPlotView, ConsensusPlotView

PANELS = {
    FoVPlotView:          'fov',
    QualityControlView:   'qc',
    BeadCleaningView:     'beads',
    CleaningView:         'cleaning',
    CyclesPlotView:       'cycles',
    PeaksPlotView:        'peaks',
    CycleHistPlotView:    'cyclehist',
    HairpinGroupPlotView: 'hairpin',
    ConsensusPlotView:    'consensus'
}

NAME   = "CyclesApp"
class HybridStatTheme(TabsTheme):
    "HybridStatTheme"
    def __init__(self):
        super().__init__("cleaning", PANELS)

@initsubclass("HybridStat:Tabs", PANELS, (CleaningView, PeaksPlotView))
class HybridStatView(TabsView[HybridStatTheme]):
    "A view with all plots"
    APPNAME = "CycleApp"
