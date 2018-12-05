#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"subtracting fixed beads from other beads"
from   typing                       import (List, Tuple, Optional, Callable,
                                            Union, Dict, cast)
import warnings

import numpy                        as     np
import pandas                       as     pd

from   data.views                   import Cycles, Beads, BEADKEY
from   model                        import PHASE
from   signalfilter                 import nanhfsigma
from   utils                        import initdefaults
from   .datacleaning                import AberrantValuesRule, HFSigmaRule, ExtentRule
from   ._core                       import (reducesignals, # pylint: disable=import-error
                                            phasebaseline)

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
    phase                               = PHASE.measure
    average                             = False
    baseline: Optional[Tuple[int, str]] = None # PHASE.initial, "median-median-median"
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
        if self.average:
            mdl = reducesignals("median", [out[j:k] for j, k in zip(pha[0], pha[2])])
            for i, _, k in zip(*pha):
                out[i:k] = mdl[i-k:]

            for i, j in zip(pha[2], pha[0][1:]):
                out[i:j] =  mdl[-1]
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


FixedData = Tuple[float, float, float, BEADKEY]
FixedList = List[FixedData]
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

    def __call__(self, beads: Beads) -> FixedList:
        """
        Creates a dataframe for all beads in  a track.
        """
        items: FixedList = []
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
        return lambda x: getsigs(cast(Dict, x.data)[0], *sigph).values

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
            return getext(cast(Dict, cycs.data)[0], extph[2], extph[3]).values
        return _fast, _slow
