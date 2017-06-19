#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Interval detection: finding flat sections in the signal"

from    typing import (NamedTuple, Optional, # pylint: disable=unused-import
                       Iterator, Iterable, Sequence, Union, Callable,
                       TYPE_CHECKING, cast)
import  numpy as np
from    numpy.lib.stride_tricks import as_strided

from    utils        import initdefaults
from    signalfilter import samples as _samples, PrecisionAlg
norm = _samples.normal.knownsigma # pylint: disable=invalid-name

class BaseSplitDetector(PrecisionAlg):
    """
    Detects flat stretches of value

    The precision is either provided or measured. In the latter case,
    the estimation used is the median-deviation of the derivate of the data.
    """
    window = 3
    @initdefaults(frozenset(locals()))
    def __init__(self, **kwa):
        super().__init__(**kwa)

    @staticmethod
    def _tointervals(nans, data, ends):
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

    @staticmethod
    def _init(data):
        nans = None
        if len(data) > 1:
            nans = np.isnan(data)
            if any(nans):
                data = data[~nans] # pylint: disable=invalid-unary-operand-type

        if len(data) <= 1:
            return None, None

        return nans, data

    def __call__(self,
                 data     : np.ndarray,
                 precision: Optional[float] = None
                ) -> np.ndarray:
        nans, tmp = self._init(data)
        if tmp is None:
            return np.empty((0,2), dtype = 'i4')
        deltas    = self._deltas(tmp)
        precision = self._precision(tmp, deltas, precision)
        threshold = self._threshold(tmp, deltas, precision)
        ends      = (deltas > threshold).nonzero()[0]
        return self._extend(self._tointervals(nans, tmp, ends), data, precision)

    @classmethod
    def run(cls, data, **kwa):
        "instantiates and calls class"
        return cls(**kwa)(data)

    def _deltas(self, data : np.ndarray) -> np.ndarray:
        "all deltas"
        window = self.window
        kern   = np.ones((window*2,))
        kern[-window:] = -1.

        delta           = np.convolve(data, kern, mode = 'same')
        delta[:window] -= np.arange(window+1)[-1:0:-1] * data[0]
        if window > 1:
            delta[1-window:] += np.arange(window)[1:] * data[-1]
        return np.abs(delta)/self.window

    def _precision(self, data:np.ndarray, _:np.ndarray, precision:Optional[float]) -> float:
        return self.getprecision(precision, data)

    def _extend(self,
                ends:np.ndarray,
                data:np.ndarray,
                precision:Optional[float]
               ) -> np.ndarray:
        return IntervalExtension.extend(ends, data, precision, self.window)

    def _threshold(self, data:np.ndarray, deltas:np.ndarray, precision:float) -> np.ndarray:
        raise NotImplementedError()

class IntervalExtension:
    """
    Extends intervals beyond the computed range up to a limit given by *window*.

    This means to remove the range size bias created by using a window to compute
    derivates.
    """
    @staticmethod
    def __right(ends, data, meds, precision, window):
        inters        = np.repeat(ends[:,1], 2)
        inters[1::2] += window
        right         = np.concatenate(np.split(data, inters)[1::2])

        right         = np.concatenate([right, [1e30]*(len(ends)*window-len(right))])
        right         = right.reshape((len(meds),window)).T

        np.abs(np.subtract(right, meds, out = right), out = right)

        right         = np.hstack([np.ones((right.shape[1],1), dtype = 'bool'),
                                   right.T < precision])
        fcn           = lambda i: np.max(np.nonzero(i)[0])
        vals          = ends[:,1]+np.apply_along_axis(fcn, 1, right)
        vals[:-1]     = np.minimum(vals[:-1], ends[1:,0]) # no merging intervals!
        return vals

    @staticmethod
    def __left(ends, data, meds, precision, window):
        inters       = np.repeat(ends[:,0], 2)
        inters[::2]  = np.maximum(0, inters[::2]-window)
        left         = np.concatenate(np.split(data, inters)[1::2])

        left         = np.concatenate([[1e30]*(len(ends)*window-len(left)), left])
        left         = left.reshape((len(meds), window)).T

        np.abs(np.subtract(left, meds, out = left), out = left)

        left         = np.hstack([left.T < precision,
                                  np.ones((left.shape[1],1), dtype = 'bool')])
        fcn          = lambda i: len(i)-np.min(np.nonzero(i)[0])-1
        vals         = ends[:,0]-np.apply_along_axis(fcn, 1, left)
        vals[1:]     = np.maximum(vals[1:], ends[:-1,1]) # no merging intervals!
        return vals

    @classmethod
    def extend(cls, ends, data, precision, window):
        "extends the provided ranges by as much as *window*"
        if window <= 1 or len(ends) < 1:
            return ends

        meds   = np.array([np.nanmedian(data[i:j]) for i, j in ends], dtype = 'f4').T
        newmax = cls.__right(ends, data, meds, precision, window)
        newmin = cls.__left (ends, data, meds, precision, window)

        over = np.nonzero(newmax[:-1] > newmin[1:])[0]
        if len(over) != 0:
            newmax[over]   = (newmin[over+1]+newmax[over])//2
            newmin[over+1] = newmax[over]

        ends[:,0] = newmin
        ends[:,1] = newmax
        return ends

class MedianThreshold:
    "A threshold relying on the deltas"
    percentile = 75.
    distance   = 3.
    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        pass

    def __call__(self, _, deltas:np.ndarray, precision:float) -> np.ndarray:
        return np.percentile(deltas, self.percentile) + self.distance*precision

class DerivateSplitDetector(BaseSplitDetector):
    """
    Detects flat stretches of value

    Flatness is defined pointwise: 2 points are flat if close enough one to the
    other. This closeness is defined using a p-value for 2 points belonging to
    the same normal distribution with a known sigma.

    The precision is either provided or measured. In the latter case,
    the estimation used is the median-deviation of the derivate of the data.
    """
    confidence = MedianThreshold() # type: Union[None, float, MedianThreshold]
    @initdefaults(frozenset(locals()))
    def __init__(self, **kwa):
        super().__init__(**kwa)

    def _precision(self,
                   data     :np.ndarray,
                   deltas   :np.ndarray,
                   precision:Optional[float]
                  ) -> float:
        if self.precision == 'deltas':
            return np.median(np.abs(deltas-np.median(deltas)))
        return self.getprecision(precision, data)

    def _threshold(self, data:np.ndarray, deltas:np.ndarray, precision:float) -> np.ndarray:
        "the threshold applied to alphas"
        if callable(self.confidence):
            return self.confidence(data, deltas, precision) # pylint: disable=not-callable

        if self.confidence is None or self.confidence <= 0.:
            return precision

        return norm.threshold(True, self.confidence, precision,
                              self.window, self.window)

class MinMaxSplitDetector(BaseSplitDetector):
    """
    Detects flat stretches of value

    Flatness is defined pointwise: 1 point is flat versus it prior if there
    exist a window *N* such that the prior *N* are lower than this and the next
    *N-1* points by a given margin (precision).

    The precision is either provided or measured. In the latter case,
    the estimation used is the median-deviation of the derivate of the data.
    """
    window     = 5
    confidence = 0.1 # type: Optional[float]
    @initdefaults(frozenset(locals()))
    def __init__(self, **kwa):
        super().__init__(**kwa)

    def _deltas(self, data   : np.ndarray) -> np.ndarray:
        "all deltas"
        window = self.window
        out    = np.empty(len(data), dtype = 'f4')
        if window == 1:
            out[0]  = 0.
            out[1:] = np.diff(data)
        else:
            dt2d = as_strided(data,
                              shape   = (len(data)-window+1, window),
                              strides = (data.strides[0],)*2)

            out[:1-window] = np.max(dt2d, axis = 1)
            out[1-window:] = [max(data[i:]) for i in range(1-window, 0)]

            out[:window]  -= [data[0]]+[min(data[:i]) for i in range(1,window)]
            out[window:]  -= np.min(dt2d, axis = 1)[:-1]
        return np.abs(out)

    def _threshold(self, data:np.ndarray, _, precision:float) -> np.ndarray:
        "the threshold applied to alphas"
        if self.confidence is None or self.confidence <= 0.:
            return precision
        return norm.threshold(True, self.confidence, precision)

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

    def __call__(self, intervals: np.ndarray) -> np.ndarray:
        edx  = self.edgelength
        minl = self.minduration
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
        "instantiates and calls class"
        return cls(**kwa)(*args)

class EventDetector(PrecisionAlg):
    "detects, mergers and selects intervals"
    split  = DerivateSplitDetector()
    merge  = EventMerger()
    select = EventSelector()
    @initdefaults(frozenset(locals()))
    def __init__(self, **kwa):
        super().__init__(**kwa)

    def __call__(self, data:np.ndarray, precision: Optional[float] = None):
        precision = self.getprecision(precision, data)
        return self.select(self.merge(data, self.split(data, precision), precision))

    @classmethod
    def run(cls, *args, **kwa):
        "instantiates and calls class"
        return cls(**kwa)(*args)
