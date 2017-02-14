#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Deals with event detection tasks"
from model          import Task, Level
from .              import EventDetectionConfig
from .alignment     import CorrelationAlignment

class EventDetectionTask(EventDetectionConfig, Task):
    u"Config for an event detection"
    levelin = Level.bead
    levelou = Level.event
    def __init__(self, **kw) -> None:
        EventDetectionConfig.__init__(self, **kw)
        Task.__init__(self)

class ExtremumAlignmentTask(Task):
    u""" Task for aligning on a given phase """
    level   = Level.cycle
    binsize = 5
    phase   = 1
    def __init__(self, **kwa):
        super().__init__()
        get          = lambda x: kwa.get(x, getattr(self.__class__, x))
        self.binsize = get('binsize')
        self.phase   = get('phase')

class CorrelationAlignmentTask(Task, CorrelationAlignment):
    u""" Task for aligning on peaks """
    level = Level.cycle
    def __init__(self, **kwa):
        Task.__init__(self)
        CorrelationAlignment.__init__(self, **kwa)
