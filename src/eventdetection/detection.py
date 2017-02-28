#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Interval detection: finding flat sections in the signal"

from    typing import (NamedTuple, Optional, # pylint: disable=unused-import
                       Iterator, Iterable, Sequence, Union, Callable, cast)
import  numpy as np
from    numpy.lib.stride_tricks import as_strided

from    utils        import initdefaults
from    signalfilter import samples as _samples, PrecisionAlg
norm = _samples.normal.knownsigma # pylint: disable=invalid-name

class SplitDetector(PrecisionAlg):
    u"""
    Detects flat stretches of value

    Flatness is defined pointwise: 2 points are flat if close enough one to the
    other. This closeness is defined using a p-value for 2 points belonging to
    the same normal distribution with a known sigma.

    The sigma (precision) is either provided or measured. In the latter case,
    the estimation used is the median-deviation of the derivate of the data.
    """
    confidence = 0.1 # type: Optional[float]
    window     = 1
    @initdefaults
    def __init__(self, **kwa):
        super().__init__(**kwa)

    def __call__(self,
                 data     : np.ndarray,
                 precision: Optional[float] = None
                ) -> np.ndarray:
        if len(data) <= 1:
            return np.empty((0,2), dtype = 'i4')

        precision = self.getprecision(precision, data)
        window    = self.window
        if self.confidence is None or self.confidence <= 0.:
            thr   = precision
        else:
            thr   = norm.threshold(True, self.confidence, precision, window, window)

        nans      = np.isnan(data)
        if any(nans):
            data = data[~nans]

        kern = np.ones((window*2,))
        kern[-window:] = -1.

        delta           = np.convolve(data, kern, mode = 'same')
        delta[:window] -= np.arange(window+1)[-1:0:-1] * data[0]
        if window > 1:
            delta[1-window:] += np.arange(window)[1:] * data[-1]

        ends = (np.abs(delta) >= (thr*window)).nonzero()[0]

        if len(ends) == 0:
            return np.array(((0,len(nans)),), dtype = 'i4')

        if len(data) < len(nans):
            # increase indexes back to former data
            ends += nans.cumsum()[~nans][ends]

        ends = np.insert(ends, [0, len(ends)], [0, len(nans)])
        ends = as_strided(ends,
                          shape   = (len(ends)-1, 2),
                          strides = (ends.strides[0],)*2)
        return ends[np.nonzero(np.diff(ends, 1).ravel() > 1)[0]]

    @classmethod
    def run(cls, data, **kwa):
        u"instantiates and calls class"
        return cls(**kwa)(data)

class EventMerger(PrecisionAlg):
    u"""
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
    @initdefaults
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

        tomerge = np.nonzero(np.diff(merge))[0]
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
        u"instantiates and calls class"
        return cls(**kwa)(*args)

class EventSelector:
    u"""
    Filters flat stretches:

    * clips the edges
    * makes sure their length is enough
    """
    edgelength = 0
    minlength  = 5
    @initdefaults
    def __init__(self, **_):
        pass

    def __call__(self, intervals: np.ndarray) -> np.ndarray:
        edx  = self.edgelength
        minl = 2*edx+self.minlength
        if minl <= 0:
            return intervals
        else:
            intervals = intervals[np.nonzero(np.diff(intervals, 1) >= minl)[0]] # type: ignore
            if edx != 0:
                intervals[:,0] += edx
                intervals[:,1] -= edx
            return intervals

    @classmethod
    def run(cls, *args, **kwa):
        u"instantiates and calls class"
        return cls(**kwa)(*args)

class EventDetector(PrecisionAlg):
    u"detects, mergers and selects intervals"
    split  = SplitDetector()
    merge  = EventMerger  ()
    select = EventSelector()
    @initdefaults
    def __init__(self, **kwa):
        super().__init__(**kwa)

    def __call__(self, data:np.ndarray, precision: Optional[float] = None):
        precision = self.getprecision(precision, data)
        return self.select(self.merge(data, self.split(data, precision), precision))

    @classmethod
    def run(cls, *args, **kwa):
        u"instantiates and calls class"
        return cls(**kwa)(*args)

IdRange = NamedTuple('IdRange', (('start', int), ('stop', int), ('cycle', int)))
def tocycles(starts, inters):
    u"""
    Assigns a cycle id to intervals. If the interval is over multiple cycles,
    one of those with the maximum number of points is chosen.

    Parameters:

    * *starts*: array of starting indexes for each cycle or track from which
    to extract that information.
    """
    if hasattr(starts, 'phase'):
        starts = starts.phase(all, 0)

    for cur in inters:
        cstart = np.searchsorted(starts,            cur.start, 'right')
        cstop  = np.searchsorted(starts[cstart-1:], cur.stop,  'right')+cstart-1

        if cstop == cstart:
            cyc = cstart
        elif cstop == cstart+1:
            cyc = cstart + (starts[cstart]-cur.start < cur.stop - starts[cstart])
        else:
            cnt    = np.diff(starts[cstart-1:cstop])
            cnt[0] = starts[cstart]-cur.start
            imax   = np.argmax(cnt)
            cyc    = cstop if cur.stop-starts[cstop-1] > cnt[imax] else cstart+imax

        yield IdRange(cur.start, cur.stop, cyc-1)

PIdRange = NamedTuple('IdRange', (('start', int), ('stop', int),
                                  ('cycle', int), ('phase', int)))
def tophaseandcycles(starts, inters):
    u"""
    Assigns a cycle and phase id to intervals. If the interval is over multiple
    cycles or phases, one of those with the maximum number of points is chosen.

    Parameters:

    * *starts*: 2D array of starting indexes for each cycle and phase, or track
    from which to extract that information.
    """
    if hasattr(starts, 'phase'):
        starts = starts.phase(all, all)

    nphases = starts.shape[1]
    yield from (PIdRange(start, stop, cycle//nphases, cycle % nphases)
                for start, stop, cycle in tocycles(starts.ravel(), inters))
