#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"""
Task for simulating tracks
"""
from typing         import Optional     # pylint: disable=unused-import
from utils          import setdefault
from model.task     import RootTask, Level
from .track         import TrackSimulatorConfig
from .peak          import PeakSimulatorConfig

class SimulatorTaskMixin:
    u"Class indicating that a track file should be added to memory"
    nbeads = 1      # type: int
    seed   = None   # type: Optional[int]
    def __init__(self, **kwa):
        setdefault(self, 'nbeads', kwa)
        setdefault(self, 'seed',   kwa)
        if hasattr(self.__class__, 'ncycles'):
            setdefault(self, 'ncycles',   kwa)

        # pylint: disable=non-parent-init-called
        RootTask.__init__(self, **kwa)
        self.__class__.__bases__[1].__init__(self, **kwa)

class TrackSimulatorTask(SimulatorTaskMixin, TrackSimulatorConfig, RootTask):
    u"Class that creates fake track data each time it is called upon"

class EventSimulatorTask(SimulatorTaskMixin, PeakSimulatorConfig, RootTask):
    u"Class that creates fake event data each time it is called upon"
    ncycles = 20    # type: int
    levelou = Level.event

class PeakSimulatorTask(SimulatorTaskMixin, PeakSimulatorConfig, RootTask):
    u"Class that creates fake peak data each time it is called upon"
    ncycles = 20    # type: int
    levelou = Level.peak
