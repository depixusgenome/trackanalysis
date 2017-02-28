#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Processors apply tasks to a data flow"
from functools          import partial
from control.processor  import Processor
from .task              import EventDetectionTask, ExtremumAlignmentTask
from .data              import Events
from .alignment         import ExtremumAlignment

class ExtremumAlignmentProcessor(Processor):
    "Aligns cycles to zero"
    tasktype = ExtremumAlignmentTask
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

class EventDetectionProcessor(Processor):
    u"Generates output from a _tasks."
    tasktype = EventDetectionTask
    def run(self, args):
        u"iterates through beads and yields cycle events"
        kwa = self.task.config()
        args.apply(lambda data: Events(track = data.track, data = data, **kwa),
                   levels = self.levels)
