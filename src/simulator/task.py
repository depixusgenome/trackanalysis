#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"""
Task for simulating tracks
"""
from typing         import Optional     # pylint: disable=unused-import
from utils          import initdefaults
from model.task     import RootTask
from .track         import TrackSimulatorConfig
from .peak          import PeakSimulatorConfig

class SimulatorTask(RootTask):
    u"Class indicating that a track file should be added to memory"
    nbeads = 1      # type: int
    seed   = None   # type: Optional[int]
    @initdefaults
    def __init__(self, **kwa):
        super().__init__(**kwa)

class TrackSimulatorTask(SimulatorTask, TrackSimulatorConfig):
    u"Class indicating that a track file should be added to memory"
    def __init__(self, **kwa) -> None:
        SimulatorTask.__init__(self, **kwa)
        TrackSimulatorConfig.__init__(self, **kwa)

class EventSimulatorTask(SimulatorTask, PeakSimulatorConfig):
    u"Class indicating that a track file should be added to memory"
    ncycles = 20    # type: int
    @initdefaults
    def __init__(self, **kwa) -> None:
        SimulatorTask.__init__(self,        **kwa)
        PeakSimulatorConfig.__init__(self,  **kwa)
