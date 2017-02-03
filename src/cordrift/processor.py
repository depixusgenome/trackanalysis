#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Processor for removing correlated drifts"

from copy              import copy, deepcopy
from functools         import wraps, partial
from typing            import (Dict, Union, Sequence,  # pylint: disable=unused-import
                               Tuple, Any, cast)

import numpy as np

from control.processor import Processor
from signalfilter      import hfsigma
from data              import Cycles, Track
from utils             import escapenans
from .task             import BeadDriftTask
from .collapse         import Range, Profile, CollapseToMean

class _BeadDriftAction:
    u"Action to be passed to a Cycles"
    _DATA    = Sequence[np.ndarray]
    tasktype = BeadDriftTask
    def __init__(self, args: Union[dict,BeadDriftTask]) -> None:
        self.cache = {}     # type: Dict[Union[int,Sequence[int]], Any]
        self.task  = cast(BeadDriftTask,
                          args if isinstance(args, self.tasktype)
                          else self.tasktype(**args))

        assert not (self.task.events is None
                    and isinstance(self.task.collapse, CollapseToMean))
        assert self.task.zero is None or self.task.zero > 2

    def __setup(self, frame:Cycles, bcopy:bool):
        task  = self.task
        frame = copy(frame).withphases(*task.phases) if bcopy else frame
        raw   = tuple(val for _, val in frame)
        if task.precision in (0, None) and {task.filter, task.events} != {None}:
            task           = deepcopy(task)
            task.precision = np.median(tuple(hfsigma(bead) for bead in raw))
        return frame, task, raw

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
    def __filter(cls, task:BeadDriftTask, raw:_DATA):
        if task.filter is None:
            return task, raw, raw

        if {getattr(task, name) for name in task.filtered} == {None}:
            return task, raw, raw

        task.filter.precision = task.precision
        fcn                   = cls.__escapenans(task.filter)
        return task, raw, tuple(fcn(cycle) for cycle in raw)

    @staticmethod
    def __collapse(frame:Cycles, task:BeadDriftTask, raw:_DATA, clean:_DATA) -> Profile:
        if task.events is None:
            events  = (Range(0, cycle) for cycle in raw)
        else:
            task.events.precision = task.precision
            choices = (lambda x, y: x), (lambda x, y: y)
            echoice = choices[1] if 'events'   in task.filtered else choices[0]
            cchoice = choices[1] if 'collapse' in task.filtered else choices[0]

            events  = (Range(evt[0], cchoice(rdt, fdt)[evt[0]:evt[1]])
                       for rdt, fdt in zip(raw, clean)
                       for evt      in task.events(echoice(rdt, fdt)))

        return task.collapse(events, Profile(frame.maxsize()))

    @staticmethod
    def __stitch(task:BeadDriftTask, raw, prof:Profile) -> Profile:
        if task.stitch is not None:
            task.stitch(prof, (Range(0, cycle) for cycle in raw))

        if task.zero is not None:
            prof.value -= np.nanmedian(prof.value[-task.zero:]) # type: ignore

        return prof

    def profile(self, frame:Cycles, bcopy:bool) -> Profile:
        u"action for removing bead drift"
        frame, task, raw   = self.__setup(frame, bcopy)
        task,  raw,  clean = self.__filter(task, raw)
        prof               = self.__collapse(frame, task, raw, clean)
        return self.__stitch(task, raw, prof)

    def __call__(self, track:Track, info:Tuple[Any,np.ndarray]):
        cycle = Cycles(track = track, data = dict((info,)))
        cycle.withphases(*self.task.phases)

        prof  = self.cache.get(info[0], None)
        if prof is None:
            self.cache[info[0]] = prof = self.profile(cycle, False)

        for _, vals in cycle:
            vals[prof.xmin:prof.xmax] -= prof.value[:len(vals)-prof.xmin]
        return info

class BeadDriftProcessor(Processor):
    u"Deals with bead drift"
    tasktype = _BeadDriftAction.tasktype
    def run(self, args):
        action = _BeadDriftAction(self.task.config())
        fcn    = lambda frame: frame.new().withaction(partial(action, frame.track),
                                                      beadonly = True)
        args.apply(fcn, levels = self.levels)

    @staticmethod
    def profile(frame:Cycles, kwa:Union[dict,BeadDriftTask]):
        u"action for removing bead drift"
        return _BeadDriftAction(kwa).profile(frame, True)
