#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Task & Processor for removing correlated drifts"
from functools              import partial
from typing                 import (Dict, Union,  # pylint: disable=unused-import
                                    Sequence, Tuple, Optional, Any, cast)
import pickle

import numpy as np

from utils                      import initdefaults
from model                      import Task, Level, PHASE
from control.processor          import Processor
from control.processor.runner   import pooledinput, poolchunk
from data                       import Track, Cycles
from eventdetection             import EventDetectionConfig
from eventdetection.detection   import EventDetector, DerivateSplitDetector
from eventdetection.data        import Events
from .collapse                  import (Range, Profile, # pylint: disable=unused-import
                                        CollapseAlg, CollapseByMerging, CollapseToMean,
                                        StitchAlg, StitchByDerivate, StitchByInterpolation)

class DriftTask(Task, EventDetectionConfig):
    "Removes correlations between cycles"
    level     = Level.bead
    phases    = PHASE.measure, PHASE.measure # type: Optional[Tuple[int,int]]
    events    = EventDetector(split = DerivateSplitDetector())
    collapse  = CollapseToMean()             # type: Optional[CollapseAlg]
    stitch    = StitchByInterpolation()      # type: Optional[StitchAlg]
    zero      = 10
    precision = 0.
    onbeads   = True
    @initdefaults(frozenset(locals()) - {'level'})
    def __init__(self, **kwa):
        Task.__init__(self)
        EventDetectionConfig.__init__(self, **kwa)

    @classmethod
    def isslow(cls) -> bool:
        "whether this task implies long computations"
        return True

class _BeadDriftAction:
    "Action to be passed to a Cycles"
    _DATA    = Sequence[np.ndarray]
    def __init__(self, args: Union[dict,DriftTask]) -> None:
        self.cache = {}     # type: Dict[Union[int,Sequence[int]], Any]
        self.task  = cast(DriftTask,
                          args if isinstance(args, DriftTask)
                          else DriftTask(**args))

        assert not (self.task.events is None
                    and isinstance(self.task.collapse, CollapseToMean))
        assert self.task.zero is None or self.task.zero > 2

    def __getstate__(self):
        return self.task.config()

    def __setstate__(self, vals):
        self.__init__(vals)

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
        "action for removing bead drift"
        data = []
        def _setcache(info):
            data.append(info[1])
            return info

        frame = frame[...].withphases(self.task.phases) if bcopy else frame
        frame.withaction(_setcache)

        prof  = self.task.collapse(self.__events(frame),
                                   Profile(frame.maxsize()))

        if self.task.stitch is not None:
            self.task.stitch(prof, (Range(0, cycle) for cycle in data))

        if self.task.zero is not None:
            prof.value -= np.nanmedian(prof.value[-self.task.zero:]) # type: ignore

        return prof

    def run(self, key, cycle:Cycles):
        "Applies the cordrift subtraction to a bead"
        prof  = self.cache.get(key, None)
        if prof is not None:
            return

        self.cache[key] = prof = self.profile(cycle, False)
        for _, vals in cycle:
            vals[prof.xmin:prof.xmax] -= prof.value[:len(vals)-prof.xmin]

    def onBead(self, track:Track, info:Tuple[Any,np.ndarray]):
        "Applies the cordrift subtraction to a bead"
        cyc = Cycles(track = track, data = dict((info,)))
        self.run((track.path, info[0]), cyc.withphases(self.task.phases))
        return info

    def onCycles(self, frame):
        "Applies the cordrift subtraction to parallel cycles"
        beads  = frame.new(data = dict(frame[...].withbeadsonly()))
        for icyc in frame.cyclerange():
            cyc = beads[...,icyc].withphases(self.task.phases)
            self.run(frame.parents+(icyc,), cyc)

        return beads.data

    def __process(self, data, nproc, iproc):
        chk = poolchunk(data.cyclerange(), nproc, iproc)
        for i in chk:
            self.run(i, data[..., i])

        sli = slice(chk[0], chk[-1]+1)
        return sli, dict(data.withcycles(sli))

    def poolOnCycles(self, pool, pickled, frame):
        "Applies the cordrift subtraction to parallel cycles"
        beads = frame.new(data = pooledinput(pool, pickled, frame[...].withbeadsonly()))
        nproc = pool.nworkers

        data = dict(beads)
        for sli, res in pool.map(partial(self.__process, beads, nproc), range(nproc)):
            for i, j in res.items():
                data[i][sli] = j

        return data

class DriftProcessor(Processor):
    "Deals with bead drift"
    _ACTION  = _BeadDriftAction
    def canpool(self):
        "returns whether this is pooled"
        return self.task.onbeads

    @classmethod
    def apply(cls, toframe = None, pool = None, data = None, **kwa):
        "applies the task to a frame or returns a function that does so"
        action = cls._ACTION(kwa)
        if kwa.get('onbeads', True):
            fcn = lambda i: (i.new().withaction(partial(action.onBead, i.track),
                                                beadsonly = True))
        elif pool is None:
            fcn = lambda i: i.new().withdata(i, action.onCycles)

        else:
            par = partial(action.poolOnCycles, pool, pickle.dumps(data))
            fcn = lambda i: i.new().withdata(i, par)
        return fcn if toframe is None else fcn(toframe)

    def run(self, args):
        if self.task.onbeads or args.pool is None:
            args.apply(self.apply(**self.config()), levels = self.levels)
        else:
            args.apply(self.apply(**args.poolkwargs(self.task),
                                  **self.config()),
                       levels = self.levels)

    @classmethod
    def profile(cls, frame:Cycles, kwa:Union[dict,DriftTask]):
        "action for removing bead drift"
        return cls._ACTION(kwa).profile(frame, True)
