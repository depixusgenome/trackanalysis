#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Task & Processor for subtracting beads from other beads"
from   typing                       import List, Iterable, TypeVar
from   abc                          import abstractmethod
from   functools                    import partial
from   itertools                    import repeat
import warnings

import numpy                        as     np

from   control.processor            import Processor
from   data.views                   import Cycles
from   model                        import Task, Level, PHASE
from   signalfilter.noisereduction  import Filter
from   utils                        import initdefaults

T = TypeVar('T', bound = 'BeadSubtractionTask')
class ISubtractionProcessor(Processor[T]):
    "Processor for subtracting beads"
    @classmethod
    @abstractmethod
    def _action(cls, task, cache, frame, info):
        pass

    @classmethod
    def apply(cls, toframe = None, cache = None, **kwa):
        "applies the subtraction to the frame"
        if toframe is None:
            return partial(cls.apply, cache = cache, **kwa)

        task    = cls.tasktype(**kwa) # pylint: disable=not-callable
        if len(task.beads) == 0:
            return toframe

        toframe = toframe.new().discarding(task.beads)
        return toframe.withaction(partial(cls._action, task, cache))

    def run(self, args):
        "updates frames"
        cache = args.data.setCacheDefault(self, {})
        args.apply(self.apply(cache =  cache, **self.config()))

    def beads(self, _, selected: Iterable[int]) -> Iterable[int]: # type: ignore
        "Beads selected/discarded by the task"
        sub = self.task.beads
        return (i for i in selected if i not in sub)

class BeadSubtractionTask(Task):
    "Task for subtracting an average signal from beads"
    filter: Filter    = None
    beads:  List[int] = []
    level             = Level.none
    @initdefaults(frozenset(locals()) - {'level'})
    def __init__(self, **kwa):
        super().__init__(**kwa)

class BeadSubtractionProcessor(ISubtractionProcessor[BeadSubtractionTask]):
    "Processor for subtracting beads"
    @classmethod
    def _action(cls, task, cache, frame, info):
        key = info[0][1] if isinstance(info[0], tuple) else None
        sub = None if cache is None else cache.get(key, None)
        if sub is None:
            data = frame.data
            itr  = task.beads if key is None else zip(task.beads, repeat(key))
            sub  = cls.aggregate([data[i] for i in itr])
            if task.filter:
                sub = task.filter(sub)
            cache[key] = sub

        out             = np.copy(info[1])
        out[:len(sub)] -= sub[:len(out)]
        return info[0], out

    @staticmethod
    def aggregate(signals):
        "Aggregates signals"
        if len(signals) == 0:
            return 0.

        if len(signals) == 1:
            res = np.copy(signals[0])
        else:
            res = np.empty(max(len(i) for i in signals), dtype = 'f4')
            ini = 0
            with warnings.catch_warnings():
                warnings.filterwarnings('ignore',
                                        category = RuntimeWarning,
                                        message  = '.*All-NaN slice encountered.*')
                while len(signals):
                    minv = min(len(i) for i in signals)
                    np.nanmean([i[ini:minv] for i in signals],
                               axis = 0, out = res[ini:minv])
                    signals = [i for i in signals if len(i) > minv]
                    ini     = minv
        return res

class MedianBeadSubtractionTask(BeadSubtractionTask):
    "Task for subtracting a median signal from beads"
    level     = Level.bead
    mainphase = PHASE.measure
    @initdefaults(frozenset(locals())-{'level'})
    def __init__(self, **kwa):
        super().__init__(**kwa)

class MedianBeadSubtractionProcessor(ISubtractionProcessor[MedianBeadSubtractionTask]):
    "Processor for subtracting beads"
    @classmethod
    def _action(cls, task, cache, frame, info):
        key = info[0][1] if isinstance(info[0], tuple) else None
        sub = None if cache is None else cache.get(key, None)
        if sub is None:
            if len(task.beads) == 1:
                sub = np.copy(frame.data[task.beads[0]])
            else:
                pha = frame.track.phases[:,task.phase:task.phase]
                cyc = frame.new(Cycles).withdata({i: frame.data[i] for i in task.beads})
                itr = [cls.aggregate([cyc[i,j] for i in task.beads], pha[j,:])
                       for j in frame.cyclerange()]
                sub = np.concatenate(itr, dtype = 'f4')

            if task.filter:
                sub = task.filter(sub)
            cache[key] = sub

        out             = np.copy(info[1])
        out[:len(sub)] -= sub[:len(out)]
        return info[0], out

    @staticmethod
    def aggregate(signals, meanrange):
        "Aggregates signals"
        assert len(signals) > 1
        rng     = slice(*meanrange)
        offsets = np.array([np.nanmedian(i[rng]) for i in signals], dtype = 'f4')
        tmp     = np.full((len(signals), max(len(i) for i in signals)), np.NaN, dtype = 'f4')

        for i, j, k in zip(tmp, signals, offsets):
            i[:len(j)] = j-k

        with warnings.catch_warnings():
            warnings.filterwarnings('ignore',
                                    category = RuntimeWarning,
                                    message  = '.*All-NaN slice encountered.*')
            res = np.nanmedian(tmp, axis = 0)

        if np.any(np.isfinite(offsets)):
            res += np.nanmean(offsets)
        return res
