#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"""
Task for simulating tracks
"""
from model.task     import RootTask, Level
from .track         import TrackSimulatorConfig

class TrackSimulatorTask(RootTask, TrackSimulatorConfig):
    u"Class indicating that a track file should be added to memory"
    levelin = Level.project
    levelou = Level.bead
    def __init__(self, **kwa) -> None:
        RootTask.__init__(self)
        TrackSimulatorConfig.__init__(self, **kwa)
        self.nbeads = kwa.get('nbeads', 1)
        self.seed   = kwa.get('seed',   None)
