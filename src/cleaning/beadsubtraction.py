#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Task & Processor for subtracting beads from other beads"
from   typing                       import List, Iterable, Tuple, Union, Callable, cast
from   functools                    import partial
from   itertools                    import repeat
import warnings

import numpy                        as     np
import pandas                       as     pd

from   control.processor            import Processor
from   data.views                   import Cycles, Beads, BEADKEY
from   model                        import Task, Level, PHASE
from   signalfilter                 import nanhfsigma
from   signalfilter.noisereduction  import Filter
from   utils                        import initdefaults
from   .datacleaning                import AberrantValuesRule, HFSigmaRule, ExtentRule
from   ._core                       import (reducesignals, # pylint: disable=import-error
                                            constant as _cleaningcst)

class SubtractAverageSignal:
    """
    Subtracts the average signal
    """
    @staticmethod
    def apply(signals, *_):
        "Aggregates signals"
        return 0. if len(signals) == 0 else reducesignals("mean", 0, 0, signals)

    @classmethod
    def process(cls, beads, frame):
        "Aggregates signals from a frame"
        signals = [frame.data[i] for i in beads]
        return 0. if len(signals) == 0 else reducesignals("mean", signals)

class SubtractWeightedAverageSignal:
    """
    Subtracts the average signal
    """
    phase = PHASE.measure
    @staticmethod
    def apply(signals, phase):
        "Aggregates signals"
        if len(signals) == 0:
            return 0.

        if len(signals) == 1:
            res = np.copy(signals[0])
        else:
            rng = slice(*phase)
            wei = np.clip(np.array([nanhfsigma(i[rng]) for i in signals], dtype = 'f4'),
                          5e-4, 1e-2)
            wei[np.isnan(wei)] = .01
            wei = (.01-wei)
            wei[np.isnan(wei)] = 0.
            res = np.zeros(max(len(i) for i in signals), dtype = 'f4')
            tot = np.zeros_like(res)
            for i, j  in zip(signals, wei):
                fin       = np.isfinite(i)
                res[fin] += i[fin]*j
                tot[fin] += fin*j
            good = tot > 1e-6
            res[good]  /= tot[good]
            res[~good]  = np.NaN
        return res

    def process(self, beads, frame):
        "Aggregates signals from a frame"
        pha = frame.track.phase.select(..., (0, self.phase, self.phase+1))
        pha = pha[:,1:]-pha[:,:1]
        cyc = frame.new(Cycles).withdata({i: frame.data[i] for i in beads})
        itr = [self.apply([cyc[i,j] for i in beads], pha[j,:])
               for j in frame.cyclerange()]

        return np.concatenate(itr)

class SubtractMedianSignal:
    """
    Subtracts a median signal from beads.

    The bias of each signal is defined as the median of phase 5 for each cycle
    independently:

    1. The bias is removed from each signal
    2. For each frame, the median of unbiased signals is selected.
    3. The average bias is added to the result
    """
    phase   = PHASE.measure
    average = False
    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        pass

    def process(self, beads, frame):
        "Aggregates signals from a frame"
        pha     = [frame.track.phase.select(..., i) for i in (0, self.phase, self.phase+1)]
        signals = [frame.data[i] for i in beads]
        if len(signals) == 0:
            return 0.

        out = reducesignals("median", signals, pha)
        if not self.average:
            return out

        mdl = reducesignals("median", [out[j:k] for j, k in zip(pha[1], pha[2])])
        for i, j, k in zip(*pha):
            out[i:j] = mdl[j-k]
            out[j:k] = mdl[j-k:]

        for i, j in zip(pha[2], pha[0][1:]):
            out[i:j] =  mdl[-1]
        out[pha[2][-1]:] = mdl[-1]
        return out

    @staticmethod
    def apply(signals, meanrange):
        "Aggregates signals"
        return (0. if len(signals) == 0 else
                reducesignals("median", meanrange[0], meanrange[1], signals))

AGG_TYPE = Union[SubtractAverageSignal, SubtractMedianSignal, SubtractWeightedAverageSignal]

class BeadSubtractionTask(Task):
    """
    Task for subtracting an average signal from beads.

    Stretches of constant values are also removed prior to the subtraction.
    See `AberrantValuesRule` for a documentation.
    """
    filter: Filter    = None
    beads:  List[int] = []
    agg:    AGG_TYPE  = SubtractMedianSignal()
    mindeltavalue     = 1e-6
    mindeltarange     = 3
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
        _cleaningcst(task, out)
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
        itr  = (cast(Iterable[int], task.beads) if key is None else
                cast(Iterable[int], list(zip(task.beads, repeat(key)))))
        if len(task.beads) == 0:
            sub = 0.

        elif len(task.beads) == 1:
            sub = np.copy(data[task.beads[0]])

        else:
            sub = task.agg.process(itr, frame)

        return task.filter(sub) if task.filter else sub

FIXED_DATA = Tuple[float, float, float, BEADKEY]
FIXED_LIST = List[FIXED_DATA]
class FixedBeadDetection:
    """
    Finds and sorts fixed beads
    """
    abberrant    = AberrantValuesRule()
    percentiles  = 5., 95.
    threshold    = 95.
    maxdiff      = .01
    diffphases   = PHASE.initial, PHASE.measure
    maxhfsigma   = .006
    maxextent    = .035
    extentphases = PHASE.initial, PHASE.pull
    @initdefaults(frozenset(locals()))
    def __init__(self, **kwa):
        pass

    def extents(self, cycles: Cycles) -> np.ndarray:
        """
        computes the bead extension
        """
        return (np.array([np.nanmax(i) for _, i in cycles.withphases(self.extentphases[1])])
                -[np.nanmin(i) for _, i in cycles.withphases(self.extentphases[0])])

    def cyclesock(self, cycles: Cycles) -> np.ndarray:
        """
        computes the cycle sock: percentiles of frame variability over all cycles
        """
        if isinstance(cycles, tuple):
            cycles = self.__cycles(cycles[0], cycles[0][cycles[1]])

        items = list(cycles.withphases(*self.diffphases).values())
        vals  = np.full((len(items), max(len(i) for i in items)), np.NaN, dtype = 'f4')
        for i, j in zip(vals, items):
            i[:len(j)]  = j
            i[:len(j)] -= np.nanmedian(j)

        return np.nanpercentile(vals, self.percentiles, axis=0)

    def dataframe(self, beads: Beads) -> pd.DataFrame:
        """
        Creates a dataframe for all beads in  a track.
        """
        ext: Tuple[List[float],...]    = ([], [] ,[])
        var: Tuple[List[float],...]    = ([], [] ,[])
        sig: Tuple[List[float],...]    = ([], [] ,[])
        isgood: List[bool] = []
        def _append(vals, itms):
            itms[0].append(np.nanmean(vals))
            itms[1].append(np.nanstd (vals))
            itms[2].append(np.nanpercentile(vals, self.threshold))

        with warnings.catch_warnings():
            warnings.filterwarnings('ignore',
                                    category = RuntimeWarning,
                                    message  = '.*All-NaN slice encountered.*')
            warnings.filterwarnings('ignore',
                                    category = RuntimeWarning,
                                    message  = '.*Mean of empty slice.*')
            for _, data in beads:
                cycs = self.__cycles(beads, data)
                _append(self.extents(cycs), ext)
                _append(np.diff(self.cyclesock(cycs), axis = 0).ravel(), var)
                _append([nanhfsigma(i) for i in cycs.values()], sig)
                isgood.append(ext[-1][-1] < self.maxextent
                              and var[-1][-1] < self.maxdiff
                              and sig[-1][-1] < self.maxhfsigma)

        _vals = lambda i, j: {i+k: l for k, l in zip(('mean', 'std', 'percentile'), j)}
        return pd.DataFrame(dict(bead = list(beads.keys()),
                                 good = isgood,
                                 **_vals('ext', ext),
                                 **_vals('var', var),
                                 **_vals('sig', sig)))

    def __call__(self, beads: Beads) -> FIXED_LIST:
        """
        Creates a dataframe for all beads in  a track.
        """
        items: FIXED_LIST = []
        sigfcn           = self.__sigs(beads)
        extfast, extslow = self.__exts(beads)

        with warnings.catch_warnings():
            warnings.filterwarnings('ignore',
                                    category = RuntimeWarning,
                                    message  = '.*All-NaN slice encountered.*')
            for beadid, data in beads:
                if extfast(data) or beads.track.rawprecision(beadid) > self.maxhfsigma:
                    continue

                cycs   = self.__cycles(beads, data)

                ext    = extslow(cycs)
                height = np.nanpercentile(ext, self.threshold)
                if height > self.maxextent:
                    continue

                delta  = np.diff(np.nanpercentile(ext, self.percentiles).ravel(),
                                 axis = 0)[0]
                if delta > self.maxdiff:
                    continue

                sigv = np.nanpercentile(sigfcn(cycs), self.threshold)
                if sigv > self.maxhfsigma:
                    continue

                delta = np.nanpercentile(np.diff(self.cyclesock(cycs), axis = 0).ravel(),
                                         self.threshold)
                if delta < self.maxdiff:
                    items.append((delta, sigv, height, beadid))
        return sorted(items)

    def __cycles(self, beads, data):
        data = np.copy(data)
        self.abberrant.aberrant(data)
        return beads[:, ...].withdata({0: data})

    def __sigs(self, beads: Beads) -> Callable[[Cycles], np.ndarray]:
        phases  = beads.track.phase.select
        getsigs = HFSigmaRule(maxhfsigma=self.maxhfsigma).hfsigma
        sigph   = tuple(phases(..., i) for i in (PHASE.initial, PHASE.measure+1))
        return lambda x: getsigs(x.data[0], *sigph).values

    def __exts(self, beads: Beads) -> Tuple[Callable[[Cycles], bool],
                                            Callable[[Cycles], np.ndarray]]:
        phases  = beads.track.phase.select
        getext  = ExtentRule(maxextent   = self.maxextent,
                             minextent   = 0.,
                             percentiles = (50,50) ).extent
        extph   = (phases(..., self.extentphases[0]+1),
                   phases(..., self.extentphases[1]),
                   phases(..., self.extentphases[0]),
                   phases(..., self.extentphases[1]+1))

        def _fast(data: np.ndarray):
            height = np.nanpercentile(data[extph[1]]-data[extph[0]], self.threshold)
            return height > self.maxextent

        def _slow(cycs: Cycles):
            return getext(cycs.data[0], extph[2], extph[3]).values
        return _fast, _slow
