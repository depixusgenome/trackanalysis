#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Task & Processor for subtracting beads from other beads"
from   typing                       import List, Iterable, Union, cast
from   functools                    import partial
from   itertools                    import repeat
import warnings

import numpy                        as     np

from   control.processor            import Processor
from   data.views                   import Cycles, Beads
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
    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        pass

    @staticmethod
    def apply(signals, meanrange):
        "Aggregates signals"
        assert len(signals) > 1
        rng     = slice(*meanrange)
        offsets = np.array([np.nanmedian(i[rng]) for i in signals], dtype = 'f4')

        if not np.any(np.isfinite(offsets)):
            return np.full(max(len(i) for i in signals), np.NaN, dtype = 'f4')

        tmp = np.full((len(signals), max(len(i) for i in signals)), np.NaN, dtype = 'f4')
        for i, j, k in zip(tmp, signals, offsets):
            i[:len(j)] = j-k

        with warnings.catch_warnings():
            warnings.filterwarnings('ignore',
                                    category = RuntimeWarning,
                                    message  = '.*All-NaN slice encountered.*')
            res = np.nanmedian(tmp, axis = 0)

            res += np.nanmean(offsets)
        return res

AGG_TYPE = Union[SubtractAverageSignal, SubtractMedianSignal]

class BeadSubtractionTask(Task):
    "Task for subtracting an average signal from beads"
    filter: Filter    = None
    beads:  List[int] = []
    agg:    AGG_TYPE  = SubtractMedianSignal()
    level             = Level.none
    def __delayed_init__(self, _):
        if isinstance(self.agg, str):
            self.agg = (SubtractMedianSignal if 'med' in self.agg.lower() else
                        SubtractAverageSignal)()

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
            sub = cls(task = task).signal(frame, key)
            if cache is not None:
                cache[key] = sub

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

    def signal(self, frame: Union[Beads, Cycles], key = None) -> np.ndarray:
        "returns the signal to subtract from beads"
        task  = self.task

        next(iter(frame.keys())) # unlazyfy # type: ignore
        data = frame.data
        if len(task.beads) == 0:
            sub = 0.

        elif len(task.beads) == 1:
            sub = np.copy(data[task.beads[0]])

        elif isinstance(task.agg, SubtractAverageSignal):
            itr  = task.beads if key is None else zip(task.beads, repeat(key))
            sub  = task.agg.apply([data[i] for i in cast(Iterable, itr)])

        elif isinstance(frame, Beads):
            pha = frame.track.phase.select(..., (0, task.agg.phase, task.agg.phase+1))
            pha = pha[:,1:]-pha[:,:1]
            cyc = frame.new(Cycles).withdata({i: data[i] for i in task.beads})
            itr = [task.agg.apply([cyc[i,j] for i in task.beads], pha[j,:])
                   for j in frame.cyclerange()]

            sub = np.concatenate(itr)
        else:
            raise NotImplementedError()

        return task.filter(sub) if task.filter else sub
