#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Processor for removing correlated drifts"

from copy              import copy
from functools         import partial
from typing            import (Dict, Union, Sequence,  # pylint: disable=unused-import
                               Tuple, Any, cast)

import numpy as np

from control.processor      import Processor
from data                   import Track, Cycles
from eventdetection.data    import Events
from .task                  import BeadDriftTask
from .collapse              import Range, Profile, CollapseToMean

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

    def __events(self, frame:Cycles) -> Events:
        if self.task.events is None:
            yield from (Range(0, cycle) for _, cycle in frame)
        else:
            events = Events(track     = frame.track,
                            data      = frame,
                            filter    = self.task.filter,
                            events    = self.task.events,
                            precision = self.task.precision)
            for _, evts in events:
                yield from (Range(evt['start'], evt['data']) for evt in evts)

    def profile(self, frame:Cycles, bcopy:bool) -> Profile:
        u"action for removing bead drift"
        data = []
        def _setcache(info):
            data.append(info[1])
            return info

        frame = copy(frame).withphases(*self.task.phases) if bcopy else frame
        frame.withaction(_setcache)

        prof  = self.task.collapse(self.__events(frame),
                                   Profile(frame.maxsize()))

        if self.task.stitch is not None:
            self.task.stitch(prof, (Range(0, cycle) for cycle in data))

        if self.task.zero is not None:
            prof.value -= np.nanmedian(prof.value[-self.task.zero:]) # type: ignore

        return prof

    def run(self, key, cycle:Cycles):
        u"Applies the cordrift subtraction to a bead"
        prof  = self.cache.get(key, None)
        if prof is  not None:
            return

        self.cache[key] = prof = self.profile(cycle, False)
        for _, vals in cycle:
            vals[prof.xmin:prof.xmax] -= prof.value[:len(vals)-prof.xmin]

    def onBead(self, track:Track, info:Tuple[Any,np.ndarray]):
        u"Applies the cordrift subtraction to a bead"
        cyc = Cycles(track = track, data = dict((info,)))
        self.run((track.path, info[0]), cyc.withphases(*self.task.phases))
        return info

    def onCycles(self, frame, first):
        u"Applies the cordrift subtraction to parallel cycles"
        assert first
        for icyc in range(frame.track.ncycles):
            cyc = frame[...,icyc]
            self.run(frame.parents+(icyc,), cyc.withphases(*self.task.phases))

class BeadDriftProcessor(Processor):
    u"Deals with bead drift"
    _ACTION  = _BeadDriftAction
    tasktype = _ACTION.tasktype
    def run(self, args):
        action = self._ACTION(self.task.config())
        if self.task.onbeads:
            fcn = lambda frame: (frame
                                 .new()
                                 .withaction(partial(action.onBead, frame.track),
                                             beadonly = True))
        else:
            fcn = lambda frame: frame.new().withdata(frame, action.onCycles)
        args.apply(fcn, levels = self.levels)

    @classmethod
    def profile(cls, frame:Cycles, kwa:Union[dict,BeadDriftTask]):
        u"action for removing bead drift"
        return cls._ACTION(kwa).profile(frame, True)
