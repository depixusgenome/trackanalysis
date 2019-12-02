#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"subtracting fixed beads from other beads"
from   dataclasses                  import dataclass
from   typing                       import (
    List, Tuple, Optional, Callable, Union, Dict, Any, cast
)
import warnings

import numpy                        as     np
import pandas                       as     pd

from   data.views                   import Cycles, Beads
from   signalfilter                 import nanhfsigma
from   utils                        import initdefaults
from   taskmodel                    import PhaseArg, PhaseRange
from   taskmodel.base               import Rescaler
from   ._core                       import (  # pylint: disable=import-error
    reducesignals, phasebaseline, dztotalcount,
    AberrantValuesRule, HFSigmaRule, ExtentRule
)

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

@dataclass
class SubtractWeightedAverageSignal:
    """
    Subtracts the average signal
    """
    phase: PhaseArg = 'measure'
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
        ind = frame.phaseindex()[self.phase]
        pha = frame.track.phase.select(..., (0, ind, ind+1))
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

    Optionally:

    * if `average` is `True`: the same process is applied to cycles as it was
    to beads.  In other words, the median behavior of cycles is measured and
    repeated for every cycle.
    * if `baseline` is `(PHASE.initial, 'median-median-median')`: a measure of
    the baseline position per cycle is computed and added to the signal. The
    measure consists in computing:

        1. taking the median (or mean: replace 1st *median* in string) of each
        phase 1 for each bead.
        2. removing the median (or mean: replace 2nd) of all measures,
        independently for each bead. Thus, phase 1 measures for each bead
        should superpose.
        3. For each frame, the median (or mean: replace 3rd) position is selected.
    """
    phase:    PhaseArg                  = 'measure'
    average:  bool                      = False
    baseline: Optional[Tuple[int, str]] = None  # PHASE.initial, "median-median-median"
    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        pass

    def process(self, beads, frame):
        "Aggregates signals from a frame"
        ind     = frame.phaseindex()[self.phase]
        pha     = [frame.track.phase.select(..., i) for i in (0, ind, ind+1)]
        signals = [frame.data[i] for i in beads]
        if len(signals) == 0:
            return 0.

        out = reducesignals("median", signals, pha)
        if self.average:
            mdl = reducesignals("median", [out[j:k] for j, k in zip(pha[0], pha[2])])
            for i, _, k in zip(*pha):
                out[i:k] = mdl[i-k:]

            for i, j in zip(pha[2], pha[0][1:]):
                out[i:j] = mdl[-1]
            out[pha[2][-1]:] = mdl[-1]

        if self.baseline is not None:
            # pylint: disable=unsubscriptable-object
            basl = phasebaseline(self.baseline[1], signals,
                                 frame.track.phase.select(..., self.baseline[0]),
                                 frame.track.phase.select(..., self.baseline[0]+1))
            for i in range(len(pha[0])-1):
                out[pha[0][i]:pha[0][i+1]] += basl[i]
            out[pha[0][-1]:] += basl[-1]
        return out

    @staticmethod
    def apply(signals, meanrange):
        "Aggregates signals"
        return (0. if len(signals) == 0 else
                reducesignals("median", meanrange[0], meanrange[1], signals))


AggType = Union[SubtractAverageSignal,
                SubtractMedianSignal,
                SubtractWeightedAverageSignal]

def aggtype(name:str) -> AggType:
    "return an aggregation"
    return (SubtractWeightedAverageSignal if 'weight' in name.lower() else
            SubtractMedianSignal          if 'med'    in name.lower() else
            SubtractAverageSignal)()


FixedData = Tuple[float, float, float, int]
FixedList = List[FixedData]


class MeasureDropsRule(Rescaler, zattributes = ('mindzdt',)):
    """
    Threshold on the number of cycles with frames in PHASE.measure such that:

        dz/dt < -mindzdt
    """
    phase:    PhaseArg = 'measure'
    maxdrops: int      = 100
    mindzdt:  float    = 1.5e-2
    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        super().__init__()

    def measure(self, track, data) -> int:
        "return the number of stairs in PHASE.measure"
        ind = track.phase[self.phase]
        ph1 = track.phase.select(..., ind)
        ph2 = track.phase.select(..., ind+1)
        return dztotalcount(-self.mindzdt, data, ph1, ph2)

    def test(self, track, data) -> bool:
        "tests the number of cycles with too many stairs"
        return self.measure(track, data) > self.maxdrops*track.ncycles//100

class FixedBeadDetection(
        Rescaler,
        zattributes = ("abberrant", "drops", 'maxdiff', 'minhfsigma', 'maxhfsigma', 'maxextent')
):
    """
    Finds and sorts fixed beads
    """
    abberrant:     AberrantValuesRule  = AberrantValuesRule()
    drops:         MeasureDropsRule    = MeasureDropsRule()
    percentiles:   Tuple[float, float] = (5., 95.)
    threshold:     float               = 95.
    maxdiff:       float               = .015
    diffphases:    PhaseRange          = ('initial', 'measure')
    minhfsigma:    float               = 1e-4
    maxhfsigma:    float               = .006
    maxextent:     float               = .035
    minpopulation: float               = 80.
    extentphases:  PhaseRange          = ('initial', 'pull')

    @initdefaults(frozenset(locals()))
    def __init__(self, **kwa):
        pass

    def config(self) -> Dict[str, Any]:
        "return the current config"
        return dict(self.__dict__)

    def extents(self, cycles: Cycles) -> np.ndarray:
        """
        computes the bead extension
        """
        return (
            np.array([np.nanmax(i) for _, i in cycles.withphases(self.extentphases[1])])
            - [np.nanmin(i) for _, i in cycles.withphases(self.extentphases[0])]
        )

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

    @staticmethod
    def population(cycs) -> float:
        "return the percentage of finite values"
        vals = sum(np.isfinite(i).sum() for i in cycs.values())
        cnt  = sum(len(i) for i in cycs.values())
        return vals/max(1,cnt)*100.

    def dataframe(self, beads: Beads) -> pd.DataFrame:  # pylint: disable=too-many-locals
        """
        Creates a dataframe for all beads in  a track.
        """
        ext1: Tuple[List[float],...] = ([], [], [])
        ext2: Tuple[List[float],...] = ([], [], [])
        var:  Tuple[List[float],...] = ([], [], [])
        sig:  Tuple[List[float],...] = ([], [], [])
        pop:    List[float] = []
        drops:  List[float] = []
        isgood: List[bool]  = []
        extfast, extslow = self.__exts(beads)

        def _append(vals, itms):
            vals = np.asarray(vals)
            good = vals[np.isfinite(vals)]
            if len(good) == 0:
                for i in itms[:3]:
                    i.append(np.NaN)
            elif len(good) == 1:
                itms[0].append(good[0])
                itms[1].append(np.NaN)
                itms[2].append(np.NaN)
            else:
                itms[0].append(np.mean(good))
                try:
                    itms[1].append(np.std(good))
                except FloatingPointError:
                    itms[1].append(np.NaN)
                itms[2].append(np.percentile(good, self.threshold))

        with warnings.catch_warnings():
            warnings.filterwarnings('ignore',
                                    category = RuntimeWarning,
                                    message  = '.*slice.*')
            for _, data in beads:
                cycs = self.__cycles(beads, data)
                pop.append(self.population(cycs))
                drops.append(self.drops.measure(cycs.track, cast(dict, cycs.data)[0]))

                _append(extslow(cycs), ext1)
                _append(extfast(data), ext2)
                _append(np.diff(self.cyclesock(cycs), axis = 0).ravel(), var)
                _append([nanhfsigma(i) for i in cycs.values()], sig)
                isgood.append(
                    ext1[-1][-1] <= self.maxextent
                    and ext2[0][-1] <= self.maxextent
                    and var[-1][-1] <= self.maxdiff
                    and self.minhfsigma <= sig[-1][-1] <= self.maxhfsigma
                )

        def _vals(i, j):
            return {i+k: l for k, l in zip(('mean', 'std', 'percentile'), j)}

        return pd.DataFrame(dict(bead = list(beads.keys()),
                                 good = isgood,
                                 pop  = pop,
                                 drops= drops,
                                 **_vals('slowext', ext1),
                                 **_vals('fastext', ext2),
                                 **_vals('var', var),
                                 **_vals('sig', sig)))

    def isfixed(
            self, beads: Beads, beadid: int, data: np.ndarray, calls = None
    ) -> Optional[FixedData]:
        """
        whether a given bead is fixed
        """
        if calls is None:
            calls = self.cache(beads)
        with warnings.catch_warnings():
            warnings.filterwarnings('ignore',
                                    category = RuntimeWarning,
                                    message  = '.*All-NaN slice encountered.*')
            return self.__isfixed(calls, beads, beadid, data)

    def __isfixed(
            self, calls, beads: Beads, beadid: int, data: np.ndarray
    ) -> Optional[FixedData]:
        extfast, extslow, sigfcn = calls
        hfs = beads.track.rawprecision(beadid)
        if  extfast(data) < self.maxextent and self.minhfsigma <= hfs <= self.maxhfsigma:
            cycs   = self.__cycles(beads, data)
            if (
                    self.population(cycs) >= self.minpopulation
                    and not self.drops.test(cycs.track, cast(dict, cycs.data)[0])
            ):

                ext    = extslow(cycs)
                height = np.nanpercentile(ext, self.threshold)
                if height <= self.maxextent:

                    delta  = np.diff(
                        np.nanpercentile(ext, self.percentiles).ravel(),
                        axis = 0
                    )[0]
                    if delta <= self.maxdiff:

                        sigv   = np.nanpercentile(sigfcn(cycs), self.threshold)
                        if self.minhfsigma <= sigv <= self.maxhfsigma:

                            delta = np.nanpercentile(
                                np.diff(self.cyclesock(cycs), axis = 0).ravel(),
                                self.threshold
                            )

                            if delta < self.maxdiff:
                                return (delta, sigv, height, beadid)
        return None

    def __call__(self, beads: Beads) -> FixedList:
        """
        Creates a dataframe for all beads in  a track.
        """
        calls = self.cache(beads)
        with warnings.catch_warnings():
            warnings.filterwarnings('ignore',
                                    category = RuntimeWarning,
                                    message  = '.*All-NaN slice encountered.*')
            tuples = (self.__isfixed(calls, beads, beadid, data) for beadid, data in beads)
            return sorted(i for i in tuples if i)

    def cache(self, frame:Beads) -> Tuple[Callable, Callable, Callable]:
        "create a tuple of functions to use during calls"
        return (*self.__exts(frame), self.__sigs(frame))

    def __cycles(self, beads, data):
        data = np.copy(data)
        self.abberrant.aberrant(data)
        return beads[:, ...].withdata({0: data})

    def __sigs(self, beads: Beads) -> Callable[[Cycles], np.ndarray]:
        phases = beads.track.phase.select
        sigs   = HFSigmaRule(minhfsigma = self.minhfsigma,
                             maxhfsigma = self.maxhfsigma).hfsigma
        ind    = beads.phaseindex('initial', 'rampdown')
        sigph  = tuple(phases(..., i) for i in ind)
        return lambda x: sigs(cast(Dict, x.data)[0], *sigph).values

    def __exts(self, beads: Beads) -> Tuple[Callable[[Cycles], bool],
                                            Callable[[Cycles], np.ndarray]]:
        phases  = beads.track.phase.select
        getext  = ExtentRule(
            maxextent   = self.maxextent,
            minextent   = 0.,
            percentiles = [100-self.threshold, self.threshold]
        ).extent
        inds    = beads.phaseindex()[self.extentphases]
        extph   = (phases(..., inds[0]+1),
                   phases(..., inds[1]),
                   phases(..., inds[0]),
                   phases(..., inds[1]+1))

        def _fast(data: np.ndarray):
            return np.nanpercentile(data[extph[1]]-data[extph[0]], self.threshold)

        def _slow(cycs: Cycles):
            return getext(cast(Dict, cycs.data)[0], extph[2], extph[3]).values
        return _fast, _slow
