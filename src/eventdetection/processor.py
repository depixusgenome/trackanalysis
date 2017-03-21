#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Processors apply tasks to a data flow"
from   functools          import partial

import numpy              as     np
from   utils              import initdefaults
from   model              import Task, Level
from   control.processor  import Processor

from   .data              import Events
from   .alignment         import ExtremumAlignment
from   .                  import EventDetectionConfig

class ExtremumAlignmentTask(Task):
    "Task for aligning on a given phase"
    level   = Level.bead
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
                                  mode    = 'max' if phase == 3 else 'min')
        def _action(frame, info):
            cycles = frame.new().withdata({info[0]: info[1]})[info[0],...]
            vals   = np.array(list(cycles.withphase(phase).values()), dtype = 'O')
            for val, delta in zip(cycles.withphase(...).values(), align(vals)):
                val += delta
            return info[0], info[1]
        args.apply(lambda frame: frame.withaction(partial(_action, frame)))

class EventDetectionTask(EventDetectionConfig, Task):
    "Config for an event detection"
    levelin = Level.bead
    levelou = Level.event
    phase   = 5
    @initdefaults('phase')
    def __init__(self, **kw) -> None:
        EventDetectionConfig.__init__(self, **kw)
        Task.__init__(self)

class EventDetectionProcessor(Processor):
    "Generates output from a _tasks."
    def run(self, args):
        "iterates through beads and yields cycle events"
        kwa          = self.task.config()
        kwa['first'] = kwa['last'] = kwa.pop('phase')
        args.apply(lambda data: Events(track = data.track, data = data, **kwa),
                   levels = self.levels)
