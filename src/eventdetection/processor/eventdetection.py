#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Processors apply tasks to a data flow"
from functools             import partial

from taskcontrol.processor import Processor
from taskmodel             import Task, Level, PHASE
from utils                 import initdefaults

from ..data                import Events
from ..                    import EventDetectionConfig

class EventDetectionTask(EventDetectionConfig, Task):
    """
    # Returned Values

    Events are returned in array with one entry per cycle. Each cycle entry consists
    in a list of events. Each event consists in a pair:

    1. the event start frame position in the `PHASE.measure`: events at the begining
    of the phase have a start position of zero.

    2. The slice of 'X', 'Y' or 'Z' data relevant to the event.
    """
    if __doc__:
        __doc__ = getattr(EventDetectionConfig, '__doc__') + __doc__

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
