#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Processor for removing correlated drifts"
import time
from copy               import deepcopy, copy

import numpy as np

from control.processor  import Processor
from signalfilter       import hfsigma
from data               import Cycles
from .task              import BeadDriftTask
from .collapse          import Range, Profile

class BeadDriftProcessor(Processor):
    u"Deals with bead drift"
    tasktype = BeadDriftTask
    _SLEEP   = 0.01
    @classmethod
    def copytask(cls, frame, kwa):
        u"copies the task and initializes its precision"
        task = cls.tasktype(**kwa)
        prec = task.precision
        if prec in (0, None):
            prec = np.median(hfsigma(bead) for bead in frame)

        for item in ('filter', 'events'):
            if getattr(task, item) is not None:
                setattr(task, item, prec)
        return task

    @classmethod
    def profile(cls, frame:Cycles, kwa:dict) -> Profile:
        u"action for removing bead drift"
        task  = cls.copytask(frame, kwa)
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
            assert task.zero > 2
            prof.value -= np.nanmedian(prof.value[-task.zero:]) # type: ignore
        return prof

    def run(self, args):
        cpy   = deepcopy(self.task)
        cache = dict()
        def _creator(frame):
            def _action(key, cycle):
                cache.setdefault(key[:-1], cycle)
                if cache[key[:-1]] is cycle:
                    cache[key[:-1]] = BeadDriftProcessor.profile(frame, cpy)

                while not isinstance(cache[key[:-1]], Profile):
                    time.sleep(self._SLEEP)

                prof = cache[key[:-1]]

                cycle[prof.xmin:prof.xmax] -= prof.value
                yield key, cycle
            return frame.withaction(_action)
        args.apply(_creator)
