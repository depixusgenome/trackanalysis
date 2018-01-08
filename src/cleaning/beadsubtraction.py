#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Task & Processor for subtracting beads from other beads"
from   typing                       import List, Iterable, Union, cast
from   functools                    import partial
from   itertools                    import repeat
import warnings

import numpy                        as     np

from   control.processor            import Processor
from   data.views                   import Cycles
from   model                        import Task, Level, PHASE
from   signalfilter.noisereduction  import Filter
from   utils                        import initdefaults

class SubtractAverageSignal:
    """
    Subtracts the average signal
    """
    @staticmethod
    def apply(signals):
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

class SubtractMedianSignal:
    """
    Subtracts a median signal from beads.

    The bias of each signal is defined as the median of phase 5 for each cycle
    independently:

    1. The bias is removed from each signal
    2. For each frame, the median of unbiased signals is selected.
    3. The average bias is added to the result
    """
    phase = PHASE.measure
    @staticmethod
    def apply(signals, meanrange):
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

AGG_TYPE = Union[SubtractAverageSignal, SubtractMedianSignal]

class BeadSubtractionTask(Task):
    "Task for subtracting an average signal from beads"
    filter: Filter    = None
    beads:  List[int] = []
    agg:    AGG_TYPE  = SubtractMedianSignal()
    level             = Level.none
    @initdefaults(frozenset(locals()) - {'level'})
    def __init__(self, **kwa):
        super().__init__(**kwa)

class BeadSubtractionProcessor(Processor[BeadSubtractionTask]):
    "Processor for subtracting beads"
    @classmethod
    def _action(cls, task, cache, frame, info):
        key = info[0][1] if isinstance(info[0], tuple) else None
        sub = None if cache is None else cache.get(key, None)
        if sub is None:
            cache[key] = sub = cls(task = task).signal(frame, key)

        out             = np.copy(info[1])
        out[:len(sub)] -= sub[:len(out)]
        return info[0], out

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

    def signal(self, frame, key = None) -> np.ndarray:
        "returns the signal"
        task = self.task
        data = frame.data
        if len(task.beads) == 1:
            sub = np.copy(data[task.beads[0]])

        elif isinstance(task.agg, SubtractAverageSignal):
            itr  = task.beads if key is None else zip(task.beads, repeat(key))
            sub  = task.agg.apply([data[i] for i in cast(Iterable, itr)])

        elif key is None:
            pha = frame.track.phases[:,task.agg.phase:task.agg.phase+1]
            cyc = frame.new(Cycles).withdata({i: data[i] for i in task.beads})
            itr = [task.agg.apply([cyc[i,j] for i in task.beads], pha[j,:])
                   for j in frame.cyclerange()]

            sub = np.concatenate(itr, dtype = 'f4')
        else:
            raise NotImplementedError()

        if task.filter:
            sub = task.filter(sub)
        return sub
