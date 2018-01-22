#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Processors apply tasks to a data flow"
from functools          import partial

from utils              import initdefaults
from model              import Task, Level, PHASE
from control.processor  import Processor

from ..data             import Events
from ..                 import EventDetectionConfig

class EventDetectionTask(EventDetectionConfig, Task):
    "Config for an event detection"
    levelin = Level.bead
    levelou = Level.event
    phase   = PHASE.measure
    @initdefaults('phase')
    def __init__(self, **kw) -> None:
        EventDetectionConfig.__init__(self, **kw)
        Task.__init__(self)

class EventDetectionProcessor(Processor[EventDetectionTask]):
    "Generates output from a _tasks."
    @classmethod
    def apply(cls, toframe, **kwa):
        "applies the task to a frame or returns a function that does so"
        if toframe is None:
            return partial(cls.apply, **kwa)

        kwa['first'] = kwa['last'] = kwa.pop('phase')
        return toframe.new(Events, **kwa)

    def run(self, args):
        "iterates through beads and yields cycle events"
        args.apply(self.apply(None, **self.task.config()), levels = self.levels)
