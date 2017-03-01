#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Processors apply tasks to a data flow"
from functools          import partial

from utils              import initdefaults
from model              import Task, Level
from control.processor  import Processor

from .data              import Events
from .alignment         import ExtremumAlignment
from .                  import EventDetectionConfig

class ExtremumAlignmentTask(Task):
    u""" Task for aligning on a given phase """
    level   = Level.cycle
    binsize = 5
    phase   = 1
    @initdefaults('binsize', 'phase')
    def __init__(self, **_):
        super().__init__()

class ExtremumAlignmentProcessor(Processor):
    "Aligns cycles to zero"
    def run(self, args):
        phase = self.task.phase
        align = ExtremumAlignment(binsize = self.task.binsize,
                                  mode    = 'max' if phase == 3 else 'min'
                                 ).one
        def _action(frame, info):
            i, j  = frame.phase(info[0][-1], [phase,phase+1])
            delta = align(info[1][i:j])
            return info[0], info[1]+delta
        args.apply(lambda frame: frame.withaction(partial(_action, frame)))

class EventDetectionTask(EventDetectionConfig, Task):
    u"Config for an event detection"
    levelin = Level.bead
    levelou = Level.event
    def __init__(self, **kw) -> None:
        EventDetectionConfig.__init__(self, **kw)
        Task.__init__(self)

class EventDetectionProcessor(Processor):
    u"Generates output from a _tasks."
    def run(self, args):
        u"iterates through beads and yields cycle events"
        kwa = self.task.config()
        args.apply(lambda data: Events(track = data.track, data = data, **kwa),
                   levels = self.levels)
