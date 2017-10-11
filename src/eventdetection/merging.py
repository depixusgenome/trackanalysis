#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Interval detection: merging and selecting the sections in the signal detected as flat"

from    typing                  import Optional, Tuple, List
from    abc                     import ABC, abstractmethod

import  numpy                   as     np
from    numpy.lib.stride_tricks import as_strided

from    utils                   import initdefaults
from    signalfilter            import samples as _samples, PrecisionAlg

class EventMerger(ABC):
    "merges neighbouring stretches of data."
    @abstractmethod
    def __call__(self,
                 data     : np.ndarray,
                 intervals: np.ndarray,
                 precision: float = None
                ) -> np.ndarray:
        pass

    @classmethod
    def run(cls, *args, **kwa):
        "instantiates and calls class"
        return cls(**kwa)(*args)

class StatsEventMerger(EventMerger):
    "merges neighbouring stretches of data."
    confidence: Optional[float] = 0.1
    oneperrange                 = True
    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        super().__init__()

    @abstractmethod
    def _initthreshold(self, data: np.ndarray, precision: Optional[float]):
        pass

    @abstractmethod
    def _initprobs(self, stats: np.ndarray):
        pass

    @abstractmethod
    def _stats(self, data: np.ndarray, index: Tuple[int, int]) -> np.ndarray:
        pass

    @staticmethod
    @abstractmethod
    def _statsupdate(stats: np.ndarray, index: Tuple[int, int]) -> np.ndarray:
        pass

    def __initstats(self, data : np.ndarray, intervals: np.ndarray):
        inds = np.insert(intervals.ravel(), intervals.size-1, len(data))
        inds = as_strided(inds,
                          shape   = (len(inds)-1, 2),
                          strides = (inds.strides[0],)*2)

        tmp  = np.apply_along_axis(lambda i: self._stats(data, i), 1, inds)
        return tmp.reshape(intervals.shape)

    @staticmethod
    def __initmerge(probs, thr) -> np.ndarray:
        merge       = np.zeros(len(probs)+2, dtype = 'bool')
        merge[1:-1] = probs < thr
        return merge

    def __intervalstomerge(self, merge, probs):
        if not any(merge):
            return np.empty(0, dtype = 'i4')

        tomerge = np.nonzero(np.logical_xor(merge[:-1], merge[1:]))[0]
        tomerge = tomerge.reshape((len(tomerge)//2, 2))

        if self.oneperrange:
            fcn           = lambda x: np.argmin(probs[x[0]:x[1]])+x[0]
            tomerge[:,0]  = np.apply_along_axis(fcn, 1, tomerge)
            tomerge[:,1]  = tomerge[:,0]+1
            merge  [1:-1]             = False
            merge  [1:][tomerge[:,0]] = True
        return tomerge

    @staticmethod
    def __updateintervals(tomerge, tokeep, intervals):
        intervals[tomerge[:,0],1] = intervals[tomerge[:,1],1]
        return intervals[tokeep]

    @classmethod
    def __updatestats(cls, tomerge, tokeep, stats):
        fcn                   = lambda i: cls._statsupdate(stats, i)
        stats[tomerge[:,0],0] = np.apply_along_axis(fcn, 1, tomerge).ravel()
        stats[tomerge[:,0],1] = stats[tomerge[:,1],1]
        return stats[tokeep]

    def __call__(self,
                 data     : np.ndarray,
                 intervals: np.ndarray,
                 precision: float = None
                ) -> np.ndarray:
        if len(data) == 0 or len(intervals) == 0:
            return np.empty((0,2), dtype = 'i4')

        thr   = self._initthreshold(data, precision)
        stats = self.__initstats(data, intervals)
        while len(intervals) > 1:
            probs   = self._initprobs(stats)
            merge   = self.__initmerge(probs, thr)

            tomerge = self.__intervalstomerge(merge, probs)
            if len(tomerge) == 0:
                break

            tokeep    = np.nonzero(~merge[:-1])[0]
            intervals = self.__updateintervals(tomerge, tokeep, intervals)
            stats     = self.__updatestats    (tomerge, tokeep, stats)

        return intervals

class KnownSigmaEventMerger(StatsEventMerger, PrecisionAlg):
    """
    Merges neighbouring stretches of data.

    Two intervals are merged whenever the mean for the second cannot be
    certified as being below that of the first. The p-value is estimated
    considering that distributions for both stretches are normal with a know
    sigma.

    The sigma (precision) is either provided or measured. In the latter case,
    the estimation used is the median-deviation of the derivate of the data.
    """
    isequal = True
    __DTYPE = np.dtype([('c', 'i4'), ('m', 'f4')])
    __NORM  = _samples.normal.knownsigma
    @initdefaults(frozenset(locals()))
    def __init__(self, **kwa):
        super().__init__(**kwa)
        PrecisionAlg.__init__(self, **kwa)

    def _initthreshold(self, data, precision):
        if self.confidence is None or self.confidence <= 0.:
            return precision
        return self.__NORM.threshold(self.isequal, self.confidence,
                                     self.getprecision(precision, data))

    def _initprobs(self, stats):
        return self.__NORM.value(self.isequal, stats[:,0])

    def _stats(self, data: np.ndarray, index: Tuple[int, int]) -> np.ndarray:
        count = (~np.isnan(data[index[0]:index[1]])).sum()
        mean  = 0. if count == 0 else np.nanmean(data[index[0]:index[1]])
        return np.array([(count, mean)], dtype = self.__DTYPE)

    @staticmethod
    def _statsupdate(stats: np.ndarray, index: Tuple[int, int]) -> np.ndarray:
        sel  = stats[index[0]:index[1]].ravel()[:-1]
        cnt  = sel['c']
        return np.array([(cnt.sum(), np.average(sel['m'], weights = cnt))],
                        dtype = stats.dtype)

class HeteroscedasticEventMerger(StatsEventMerger):
    """
    Merges neighbouring stretches of data.

    Two intervals are merged whenever the mean for the second cannot be
    certified as being below that of the first. The p-value is estimated
    considering that distributions for both stretches are normal with a possibly
    different sigma.
    """
    __DTYPE      = np.dtype([('c', 'i4'), ('m', 'f4'), ('s', 'f4')])
    __NORM       = _samples.normal.heteroscedastic
    minprecision = 5e-4
    def _initthreshold(self, _1, _2):
        return self.__NORM.threshold(self.confidence)

    def _initprobs(self, stats):
        return self.__NORM.thresholdvalue(stats[:,0])

    @staticmethod
    def _initmerge(probs, thr) -> np.ndarray:
        merge       = np.zeros(len(probs)+2, dtype = 'bool')
        merge[1:-1] = probs < thr
        return merge

    def _stats(self, data: np.ndarray, index: Tuple[int, int]) -> np.ndarray:
        count = (~np.isnan(data[index[0]:index[1]])).sum()
        mean  = 0. if count == 0 else np.nanmean(data[index[0]:index[1]])
        std   = 0. if count == 0 else np.nanstd(data[index[0]:index[1]])
        return np.array([(count, mean, max(self.minprecision, std))], dtype = self.__DTYPE)

    @staticmethod
    def _statsupdate(stats: np.ndarray, index: Tuple[int, int]) -> np.ndarray:
        sel  = stats[index[0]:index[1]].ravel()[:-1]
        cnt  = sel['c']
        return np.array([(cnt.sum(),
                          np.average(sel['m'], weights = cnt),
                          np.average(sel['s'], weights = cnt))],
                        dtype = stats.dtype)

class PopulationMerger(EventMerger):
    """
    Merges neighbouring stretches of data if enough of their population have a
    common range.
    """
    percentile = 75.
    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        super().__init__()

    def __call__(self,
                 data     : np.ndarray,
                 intervals: np.ndarray,
                 _: float = None
                ) -> np.ndarray:

        rem   = np.ones(len(intervals), dtype = 'bool')
        cnt   = 0
        while rem.sum() != cnt:
            cnt   = rem.sum()
            self.__apply(data, intervals, rem)
        return intervals[rem]

    def __apply(self, data, intervals, rem):
        stats = lambda i: (data[i[0]:i[1]],
                           np.nanmin(data[i[0]:i[1]]),
                           np.nanmax(data[i[0]:i[1]]))
        ileft = 0
        left  = stats(intervals[0])
        for iright in range(1, len(intervals)):
            if not rem[iright]:
                continue

            right = stats(intervals[iright])
            if not (left[1] <= right[1] <= left[2]
                    or left[1]  <= right[2] <= left[2]
                    or right[1] <= left[1]  <= right[2]
                    or right[1] <= left[2]  <= right[2]):
                ileft, left = iright, right
                continue

            todo = ((left, right), (right, left))
            if len(left[0]) < len(right[0]):
                todo = todo[::-1]

            for one, other in todo:
                good = other[0][np.isfinite(other[0])]
                both = np.logical_and(good >= one[1], good <= one[2])
                nmin = int(len(good) * self.percentile * 1e-2+.5)
                if nmin == len(good) and nmin > 1:
                    nmin = len(good)-2
                if nmin <= both.sum():
                    rem[iright]      = False
                    intervals[ileft] = intervals[ileft][0], intervals[iright][1]
                    left             = (data[intervals[ileft][0]:intervals[ileft][1]],
                                        left[1], right[2])

                    break
            else:
                ileft, left = iright, right

class MultiMerger(EventMerger):
    "Multiple merge tools applied in a row"
    merges: List[EventMerger] = [HeteroscedasticEventMerger(), PopulationMerger()]
    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        super().__init__()

    def __call__(self,
                 data     : np.ndarray,
                 intervals: np.ndarray,
                 precision: float = None
                ) -> np.ndarray:
        for merge in self.merges:
            intervals = merge(data, intervals, precision)
        return intervals

class EventSelector:
    """
    Filters flat stretches:

    * clips the edges
    * makes sure their length is enough
    """
    edgelength = 0
    minlength  = 5
    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        pass

    @property
    def minduration(self) -> int:
        "returns 2*edgelength+minlength"
        return 2*self.edgelength+self.minlength

    @staticmethod
    def __good(minl, data):
        return (np.all(np.isfinite(data[[0,-1]]))
                or np.diff(np.nonzero(np.isfinite(data))[0][[0,-1]]) >= minl-1)

    def __call__(self, data: np.ndarray, intervals: np.ndarray) -> np.ndarray:
        edx  = self.edgelength
        minl = self.minduration
        if minl <= 0:
            return intervals
        else:
            intervals = intervals[np.nonzero(np.diff(intervals, 1) >= minl)[0]] # type: ignore
            good      = np.fromiter((self.__good(minl, data[slice(*rng)]) for rng in intervals),
                                    'bool', len(intervals))
            intervals = intervals[good]
            if edx != 0:
                intervals[:,0] += edx
                intervals[:,1] -= edx
            return intervals

    @classmethod
    def run(cls, *args, **kwa):
        "instantiates and calls class"
        return cls(**kwa)(*args)
