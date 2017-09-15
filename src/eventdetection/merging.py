#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Interval detection: merging and selecting the sections in the signal detected as flat"

from    typing import Optional

import  numpy as np
from    numpy.lib.stride_tricks import as_strided

from    utils        import initdefaults
from    signalfilter import samples as _samples, PrecisionAlg
norm = _samples.normal.knownsigma # pylint: disable=invalid-name

class EventMerger(PrecisionAlg):
    """
    Merges neighbouring stretches of data.

    Two intervals are merged whenever the mean for the second cannot be
    certified as being below that of the first. The p-value is estimated
    considering that distributions for both stretches are normal with a know
    sigma.

    The sigma (precision) is either provided or measured. In the latter case,
    the estimation used is the median-deviation of the derivate of the data.
    """
    confidence  = 0.1  # type: Optional[float]
    isequal     = True
    oneperrange = True
    @initdefaults(frozenset(locals()))
    def __init__(self, **kwa):
        super().__init__(**kwa)

    @staticmethod
    def __initstats(data : np.ndarray, intervals: np.ndarray):
        inds     = np.insert(intervals.ravel(), intervals.size-1, len(data))
        inds     = as_strided(inds,
                              shape   = (len(inds)-1, 2),
                              strides = (inds.strides[0],)*2)

        dtype    = np.dtype([('c', 'i4'), ('m', 'f4')])
        def _stats(i):
            count = (~np.isnan(data[i[0]:i[1]])).sum()
            mean  = 0. if count == 0 else np.nanmean(data[i[0]:i[1]])
            return np.array([(count, mean)], dtype = dtype)

        tmp = np.apply_along_axis(_stats, 1, inds)
        return tmp.reshape(intervals.shape)

    def __initprobs(self, stats):
        fcn = lambda i: norm.value(self.isequal, stats[i,0], stats[i+1,0])
        siz = len(stats)-1
        return np.fromiter((fcn(i) for i in range(siz)), dtype = 'f4', count = siz)

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
    def __updatestats(tomerge, tokeep, stats):
        dtype = stats.dtype
        def _update(rng):
            sel  = stats[rng[0]:rng[1]].ravel()[:-1]
            cnt  = sel['c']
            return np.array([(cnt.sum(), np.average(sel['m'], weights = cnt))],
                            dtype = dtype)

        stats[tomerge[:,0],0] = np.apply_along_axis(_update, 1, tomerge).ravel()
        stats[tomerge[:,0],1] = stats[tomerge[:,1],1]
        return stats[tokeep]

    @staticmethod
    def __updateintervals(tomerge, tokeep, intervals):
        intervals[tomerge[:,0],1] = intervals[tomerge[:,1],1]
        return intervals[tokeep]

    def __call__(self,
                 data     : np.ndarray,
                 intervals: np.ndarray,
                 precision: Optional[float] = None
                ) -> np.ndarray:
        if len(data) == 0 or len(intervals) == 0:
            return np.empty((0,2), dtype = 'i4')

        if self.confidence is None or self.confidence <= 0.:
            thr = precision
        else:
            thr = norm.threshold(self.isequal, self.confidence,
                                 self.getprecision(precision, data))
        stats = self.__initstats(data, intervals)
        while len(intervals) > 1:
            probs       = self.__initprobs(stats)
            merge       = np.zeros(len(intervals)+1, dtype = 'bool')
            merge[1:-1] = probs < thr


            tomerge     = self.__intervalstomerge(merge, probs)
            if len(tomerge) == 0:
                break

            tokeep    = np.nonzero(~merge[:-1])[0]
            intervals = self.__updateintervals(tomerge, tokeep, intervals)
            stats     = self.__updatestats    (tomerge, tokeep, stats)

        return intervals

    @classmethod
    def run(cls, *args, **kwa):
        "instantiates and calls class"
        return cls(**kwa)(*args)

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
