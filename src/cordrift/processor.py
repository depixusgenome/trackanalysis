#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Task & Processor for removing correlated drifts"
from functools              import partial
from typing                 import (Dict, Union,  # pylint: disable=unused-import
                                    Sequence, Tuple, Optional, Any, cast)

import numpy as np

from utils                      import initdefaults
from model                      import Task, Level, PHASE
from control.processor          import Processor
from control.processor.runner   import pooledinput, poolchunk, pooldump
from data                       import Track, Cycles
from signalfilter               import rawprecision
from eventdetection             import EventDetectionConfig
from eventdetection.detection   import EventDetector
from eventdetection.data        import Events
from .collapse                  import (Range, Profile, # pylint: disable=unused-import
                                        CollapseAlg, CollapseByMerging, CollapseToMean,
                                        StitchAlg, StitchByDerivate, StitchByInterpolation)

class DriftTask(Task, EventDetectionConfig):
    "Removes correlations between cycles"
    level     = Level.bead
    phases    = PHASE.measure, PHASE.measure # type: Optional[Tuple[int,int]]
    events    = EventDetector()
    collapse  = CollapseToMean()             # type: Optional[CollapseAlg]
    stitch    = StitchByInterpolation()      # type: Optional[StitchAlg]
    zero      = 10
    precision = None
    rawfactor = 1.
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
    def __init__(self, args: Union[dict,DriftTask], cache = None) -> None:
        self.cache = {} if cache is None else cache # type: Dict[Union[int,Sequence[int]], Any]
        self.done  = set()                          # type: set
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
            yield from (Range(0, i) for _, i in frame)
        else:
            for _, evts in frame.new(Events, **self.task.config()):
                yield from (Range(*i) for i in evts)

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
        if key in self.done:
            return

        self.done.add(key)
        prof = self.cache.get(key, None)
        if prof is None:
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

    def poolOnCycles(self, pool, pickled, frame):
        "Applies the cordrift subtraction to parallel cycles"
        rawprecision(frame.track, frame[...].withbeadsonly().keys()) # compute & freeze precisions
        if getattr(frame.cycles, 'start', None) is not None:
            raise NotImplementedError("*you* do it!")

        orig   = frame.new(data   = pooledinput(pool, pickled, frame),
                           cycles = frame.cycles)

        rng    = list(orig.cyclerange())
        beads  = orig[...].withbeadsonly().withcycles(...)
        cycles = []
        for iproc in range(pool.nworkers):
            chk = poolchunk(rng, pool.nworkers, iproc)
            tmp = beads[..., chk].withphases(self.task.phases)
            cycles.append(tmp.new(data = dict(tmp), direct = True))

        for cyc, done in zip(cycles, pool.map(self._process, cycles)):
            for i, j in done.items():
                cyc[i][:] = j

        return dict(orig)

    def _process(self, data):
        for i in set(i for _, i in data.keys()):
            self.run(i, data[..., i])
        return dict(data)

class DriftProcessor(Processor):
    "Deals with bead drift"
    _ACTION  = _BeadDriftAction
    def canpool(self):
        "returns whether this is pooled"
        return self.task.onbeads

    @classmethod
    def apply(cls, toframe = None, pool = None, data = None, cache = None, **kwa):
        "applies the task to a frame or returns a function that does so"
        action = cls._ACTION(kwa, cache = cache)
        if kwa.get('onbeads', True):
            fcn = lambda i: (i.new().withaction(partial(action.onBead, i.track),
                                                beadsonly = True))
        elif pool is None:
            fcn = lambda i: i.new().withdata(i, action.onCycles)

        else:
            par = partial(action.poolOnCycles, pool, pooldump(data))
            fcn = lambda i: i.new().withdata(i, par)
        return fcn if toframe is None else fcn(toframe)

    def run(self, args):
        kwa          = self.config()
        kwa['cache'] = args.data.setCacheDefault(self, {})
        if not (self.task.onbeads or args.pool is None):
            kwa.update(args.poolkwargs(self.task))

        args.apply(self.apply(**kwa), levels = self.levels)

    @classmethod
    def profile(cls, frame:Cycles, kwa:Union[dict,DriftTask]):
        "action for removing bead drift"
        return cls._ACTION(kwa).profile(frame, True)
