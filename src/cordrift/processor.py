#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Processor for removing correlated drifts"
import time
import threading
from   copy             import copy, deepcopy
from   functools        import wraps, partial
from   typing           import (Dict, Union, Sequence, Any) # pylint: disable=unused-import

import numpy as np

from control.processor  import Processor
from signalfilter       import hfsigma
from data               import Cycles
from utils              import escapenans
from .task              import BeadDriftTask
from .collapse          import Range, Profile, CollapseToMean

class BeadDriftAction:
    u"Action to be passed to a Cycles"
    _SLEEP   = 0.01
    tasktype = BeadDriftTask
    def __init__(self, args: dict) -> None:
        self.cache = {} # type: Dict[Union[int,Sequence[int]], Any]
        self.lock  = threading.Lock()
        self.task  = args if isinstance(args, self.tasktype) else self.tasktype(**args)
        assert not (self.task.events is None
                    and isinstance(self.task.collapse, CollapseToMean))
        assert self.task.zero is None or self.task.zero > 2

    def __call__(self, frame, info):
        parent = info[0][:-1]
        prof   = None
        with self.lock:
            self.cache.setdefault(parent, parent)

        if self.cache[parent] is parent:
            self.cache[parent] = prof = self.profile(frame)

        while not isinstance(prof, Profile):
            time.sleep(self._SLEEP)
            prof = self.cache[parent]

        if self.task.phases:
            ind1 = frame.phaseid(info[0][-1], self.task.phases[0])
            ind2 = frame.phaseid(info[0][-1], self.task.phases[1])
            info[1][ind1:ind2] -= prof.value[:ind2-ind1]
        else:
            info[1] -= prof.value[:len(info[1])]
        return info

    def __setup(self, frame):
        task  = self.task
        frame = copy(frame).withphases(*task.phases)
        raw   = tuple(val for _, val in frame)
        if task.precision in (0, None) and {task.filter, task.events} != {None}:
            task = deepcopy(task)
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

    def profile(self, frame:Cycles) -> Profile:
        u"action for removing bead drift"
        task, raw        = self.__setup(frame)
        task, raw, clean = self.__filter(task, raw)
        prof             = self.__collapse(task, raw, clean)
        return self.__stitch(task, raw, prof)

class BeadDriftProcessor(Processor):
    u"Deals with bead drift"
    tasktype = BeadDriftTask
    def run(self, args):
        action = BeadDriftAction(self.task.config())
        fcn    = lambda frame: (frame
                                .new()
                                .withaction(partial(action, frame), beadonly = True))
        args.apply(fcn, levels = self.levels)

    @staticmethod
    def profile(frame, kwa):
        u"action for removing bead drift"
        return BeadDriftAction(kwa).profile(frame)
