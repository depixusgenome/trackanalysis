#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Processor for removing correlated drifts"
import time
import threading
from   copy             import copy
from   functools        import wraps

import numpy as np

from control.processor  import Processor
from signalfilter       import hfsigma
from data               import Cycles
from utils              import escapenans
from .task              import BeadDriftTask
from .collapse          import Range, Profile, CollapseToMean

class BeadDriftProcessor(Processor):
    u"Deals with bead drift"
    tasktype = BeadDriftTask
    _SLEEP   = 0.01

    @classmethod
    def __setup(cls, frame, kwa):
        task = kwa if isinstance(kwa, cls.tasktype) else cls.tasktype(**kwa)
        assert not (task.events is None and isinstance(task.collapse, CollapseToMean))
        assert task.zero is None or task.zero > 2

        frame = copy(frame).withphases(*task.phases)
        raw   = tuple(val for _, val in frame)
        if task.precision in (0, None) and {task.filter, task.events} != {None}:
            task.precision = np.median(tuple(hfsigma(bead) for bead in raw))
        return task, raw

    @staticmethod
    def __escapenans(fcn):
        @wraps(fcn)
        def _fcn(cycle):
            cycle = np.copy(cycle)
            with escapenans(cycle) as arr:
                fcn(arr)
            return cycle
        return _fcn

    @classmethod
    def __filter(cls, task, raw):
        if task.filter is None:
            return task, raw, raw

        if {getattr(task, name) for name in task.filtered} == {None}:
            return task, raw, raw

        task.filter.precision = task.precision
        fcn                   = cls.__escapenans(task.filter)
        return task, raw, tuple(fcn(cycle) for cycle in raw)


    @staticmethod
    def __collapse(task, raw, clean):
        if task.events is None:
            events = (Range(0, cycle) for cycle in raw)
        else:
            task.events.precision = task.precision
            choices = (lambda x, y: x), (lambda x, y: y)
            echoice =  choices['events'     in task.filtered]
            cchoice =  choices['collapse'   in task.filtered]

            events = (Range(evt[0], cchoice(rdt, fdt)[evt[0]:evt[1]])
                      for rdt, fdt in zip(raw, clean)
                      for evt      in task.events(echoice(rdt, fdt)))

        return task.collapse(events)

    @staticmethod
    def __stitch(task, raw, prof):
        if task.stitch is not None:
            task.stitch(prof, (Range(0, cycle) for cycle in raw))

        if task.zero is not None:
            prof.value -= np.nanmedian(prof.value[-task.zero:]) # type: ignore

        return prof

    @classmethod
    def profile(cls, frame:Cycles, kwa:dict) -> Profile:
        u"action for removing bead drift"
        task, raw        = cls.__setup(frame, kwa)
        task, raw, clean = cls.__filter(task, raw)
        prof             = cls.__collapse(task, raw, clean)
        return cls.__stitch(task, raw, prof)

    def run(self, args):
        cpy   = self.task.config()
        cache = dict()
        lock  = threading.Lock()
        def _creator(frame):
            def _action(key, cycle):
                parent = key[:-1]
                prof   = None

                with lock:
                    cache.setdefault(parent, parent)

                if cache[parent] is parent:
                    cache[parent] = prof = BeadDriftProcessor.profile(frame, cpy)

                while not isinstance(prof, Profile):
                    time.sleep(self._SLEEP)
                    prof = cache[parent]

                if cpy.phases:
                    ind1 = frame.phaseid(key[-1], cpy.phases[0])
                    ind2 = frame.phaseid(key[-1], cpy.phases[1])
                    cycle[ind1:ind2] -= prof.value[:ind2-ind1]
                else:
                    cycle -= prof.value[:len(cycle)]
                return key, cycle

            return frame.withaction(_action)

        args.apply(_creator)
