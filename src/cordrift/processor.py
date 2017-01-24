#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Processor for removing correlated drifts"
from copy               import deepcopy, copy

import numpy as np

from control.processor  import Processor
from signalfilter       import hfsigma
from .task              import BeadDriftTask
from .collapse          import Range

class BeadDriftProcessor(Processor):
    u"Deals with bead drift"
    tasktype = BeadDriftTask
    @classmethod
    def profile(cls, frame, kwa):
        u"action for removing bead drift"
        if kwa['precision'] == 0:
            kwa['precision'] = np.median(hfsigma(bead) for bead in frame)
        task = cls.tasktype(**kwa)

        data  = dict(copy(frame)
                     .withcopy    (task.filter is not None)
                     .withfunction(task.filter, beadonly = True)
                     .withphases  (*task.phases))

        if task.events is None:
            events = (Range(0, cycle) for cycle in data.values())
        else:
            events = (Range(evt.start, cycle[evt])
                      for cycle in data.values()
                      for evt   in task.events(cycle))

        prof = task.collapse(events)
        if task.stitch is not None:
            events = (Range(0, cycle) for cycle in data.values())
            prof   = task.stitch(prof, events)

        if task.zero is not None:
            prof.value -= np.nanmedian(prof.value[-task.zero:])
        return prof

    def run(self, args):
        items = deepcopy(self.task.__dict__)
        cache = dict()
        def _creator(frame):
            def _action(key, cycle):
                if key[:-1] not in cache:
                    cache[key[:-1]] = BeadDriftProcessor.profile(frame, items)
                prof = cache[key[:-1]]
                cycle[prof.xmin:prof.xmax] -= prof.value
                yield key, cycle
            return frame.withaction(_action)
        args.apply(_creator)
