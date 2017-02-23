#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"""
Task for simulating tracks
"""
from typing         import Optional     # pylint: disable=unused-import
from utils          import initdefaults
from model.task     import RootTask, Level
from .track         import TrackSimulator

class _SimulatorTask(TrackSimulator):
    u"Class indicating that a track file should be added to memory"
    nbeads = 1      # type: int
    seed   = None   # type: Optional[int]
    @initdefaults
    def __init__(self, **kwa):
        super().__init__(**kwa)
        RootTask.__init__(self, **kwa) # pylint: disable=non-parent-init-called

class TrackSimulatorTask(_SimulatorTask, RootTask):
    u"Class that creates fake track data each time it is called upon"

class EventSimulatorTask(_SimulatorTask, RootTask):
    u"Class that creates fake event data each time it is called upon"
    ncycles = 20    # type: int
    levelou = Level.event

class ByPeaksEventSimulatorTask(_SimulatorTask, RootTask):
    u"Class that creates fake peak data each time it is called upon"
    ncycles = 20    # type: int
    levelou = Level.peak
