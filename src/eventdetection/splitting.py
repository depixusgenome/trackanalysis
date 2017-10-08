#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Interval detection: splitting the trace into flat events"

from    typing import (Optional, # pylint: disable=unused-import
                       Tuple, Union, Callable)

import  numpy as np
from    numpy.lib.stride_tricks import as_strided
from    scipy.ndimage.filters   import correlate1d

from    utils        import initdefaults
from    signalfilter import samples as _samples, PrecisionAlg
norm = _samples.normal.knownsigma # pylint: disable=invalid-name

class IntervalExtension:
    """
    Extends intervals beyond the computed range up to a limit given by *window*.

    This means to remove the range size bias created by using a window to compute
    derivates.
    """
    @classmethod
    def extend(cls, ends, data, precision, window):
        "extends the provided ranges by as much as *window*"
        if window <= 1 or len(ends) < 1:
            return ends

        newmin = cls.__apply(ends, data, precision, -window)
        newmax = cls.__apply(ends, data, precision,  window)

        over   = np.nonzero(newmax[:-1] > newmin[1:])[0]
        if len(over) != 0:
            newmax[over]   = (newmin[over+1]+newmax[over])//2
            newmin[over+1] = newmax[over]

        ends[:,0] = newmin
        ends[:,1] = newmax
        return ends

    def __call__(self, ends, data, precision, window):
        return self.extend(ends, data, precision, window)

    @staticmethod
    def _sidedata(inters, data, window, default, imax = None):
        side   = 1 if window > 0 else 0
        inters = np.repeat(inters, 2)
        out    = inters[side::2]
        out   += window
        if   window < 0:
            np.maximum(0         if imax is None else imax, out, out = out)
        else:
            np.minimum(len(data) if imax is None else imax, out, out = out)

        rngs = np.split(data, inters)[1::2]
        diff = abs(window)-np.diff(inters)[::2]
        inds = np.nonzero(diff)[0][::-1]
        for i, j in zip(inds, diff[inds]):
            rngs.insert(i+side, [default]*j)
        return np.concatenate(rngs).reshape((len(inters)//2, abs(window))).T

    @classmethod
    def __apply(cls, ends, data, precision, window):
        side = 1 if window > 0 else 0
        inds = ends[:,side], ends[:,1-side]

        test = cls._test(inds, data, precision, window)
        good = np.ones((test.shape[0], 1), dtype = 'bool')
        test = np.hstack([good, test] if side else [test, good])

        if side:
            fcn = lambda i: np.max(np.nonzero(i)[0])
        else:
            fcn = lambda i: np.min(np.nonzero(i)[0])+1-len(i)
        res = inds[0]+np.apply_along_axis(fcn, 1, test)

        if side:
            res[:-1] = np.minimum(res[:-1], inds[1][1:])  # no merging intervals!
        else:
            res[1:]  = np.maximum(res[1:],  inds[1][:-1]) # no merging intervals!
        return res

    @classmethod
    def _test(cls, inds, data, precision, window):
        raise NotImplementedError()

class IntervalExtensionAroundMean(IntervalExtension):
    """
    Extends intervals beyond the computed range up to a limit given by *window*.
    The range is extended:

        1. by at most *window* points in any direction.
        2. up to and including the farthest point within *mean ± precision*
        where the mean is the average of the *window* points at the interval edge.

        For a window of 3, where upper triangles are the current selection, the
        range is extended to the left by 2 (up to ☺)

            ^
            |   X
            |              △
            |
            |     ⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯
            |                 △
            |     ☺
            |     ⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯
            |
            |           △
            |
            |       X
            +----------------------->
    This means to remove the range size bias created by using a window to compute
    derivates.
    """
    @classmethod
    def _test(cls, inds, data, precision, window):
        vals = cls._sidedata(inds[0], data, window, 1e30)
        meds = np.nanmean(cls._sidedata(inds[0], data, -window, np.NaN, inds[1]), 0)

        np.abs(np.subtract(vals, meds, out = vals), out = vals)
        vals[np.isnan(vals)] = 0.
        return (vals < precision).T

class IntervalExtensionAroundRange(IntervalExtension):
    """
    Extends intervals beyond the computed range up to a limit given by *window*.
    The range is extended:

        1. by at most *window* points in any direction.
        2. up to and including the farthest point within *mean ± precision*
        where the mean is the average of the *window* points at the interval edge.
        2. up to and including the farthest point within in the same range of values
        as the *window* points at the interval edge:

        For a window of 3, where upper triangles are the current selection, the
        range is extended to the left by 2 (up to ☺)

            ^
            |   X
            |     ⋯⋯⋯⋯⋯⋯⋯⋯ △
            |
            |
            |                   △
            |     ☺
            |
            |     ⋯⋯⋯⋯⋯ △
            |
            |       X
            +----------------------->



    This means to remove the range size bias created by using a window to compute
    derivates.
    """
    @classmethod
    def _test(cls, inds, data, precision, window):
        vals  = cls._sidedata(inds[0], data, window, 1e30)

        refs  = cls._sidedata(inds[0], data, -window, np.NaN, inds[1])
        refs[0, np.all(np.isnan(refs), 0)] = np.finfo('f4').max

        meanv = np.nanmean(refs, 0)
        maxv  = np.maximum(np.nanmax(refs, 0), meanv+precision)
        minv  = np.minimum(np.nanmin(refs, 0), meanv-precision)
        vals[np.isnan(vals)] = 0.
        return np.logical_and(vals <= maxv, vals >= minv).T

class BaseSplitDetector(PrecisionAlg):
    """
    Detects flat stretches of value

    The precision is either provided or measured. In the latter case,
    the estimation used is the median-deviation of the derivate of the data.
    """
    window  = 3
    extend  = IntervalExtensionAroundRange() # type: Optional[IntervalExtension]
    @initdefaults(frozenset(locals()))
    def __init__(self, **kwa):
        super().__init__(**kwa)

    @staticmethod
    def _tointervals(nans, data, alldata, ends):
        if len(ends) == 0:
            return np.array(((0,len(nans)),), dtype = 'i4')

        if len(data) < len(nans):
            # increase indexes back to former data
            ends += nans.cumsum()[~nans][ends]

        ends = np.insert(ends, [0, len(ends)], [0, len(nans)])
        ends = as_strided(ends,
                          shape   = (len(ends)-1, 2),
                          strides = (ends.strides[0],)*2)
        ends = ends[np.nonzero(np.diff(ends, 1).ravel() > 1)[0]]
        return ends[[np.any(np.isfinite(alldata[slice(*i)])) for i in ends]]

    @staticmethod
    def _init(data:np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        nans = None
        if len(data) > 1:
            nans = np.isnan(data)
            if any(nans):
                data = data[~nans] # pylint: disable=invalid-unary-operand-type

        return (np.array([]),)*2 if len(data) <= 1 else nans, data

    def __call__(self,
                 data     : np.ndarray,
                 precision: Optional[float] = None
                ) -> np.ndarray:
        nans, tmp = self._init(data)
        if len(tmp) == 0:
            return np.empty((0,2), dtype = 'i4')
        deltas    = self._deltas(tmp)
        precision = self._precision(tmp, deltas, precision)
        threshold = self._threshold(tmp, deltas, precision)
        ends      = self._tointervals(nans, tmp, data, (deltas > threshold).nonzero()[0])
        if self.extend is not None:
            return self.extend(ends, data, precision, self.window)
        return ends

    def grade(self, data : np.ndarray, precision: float = None) -> np.ndarray:
        """
        Returns the likeliness of an interval being declared.

        Values above one define an interval boundary.
        """
        nans, tmp = self._init(data)
        if len(tmp) == 0:
            return np.full((len(data),), np.NaN, dtype = 'f4')

        deltas    = self._deltas(tmp)
        precision = self._precision(tmp, deltas, precision)
        deltas   /= self._threshold(tmp, deltas, precision)
        if len(data) == len(nans):
            return deltas

        result        = np.full((len(data),), np.NaN, dtype = 'f4')
        result[~nans] = deltas
        return result

    @classmethod
    def run(cls, data, **kwa):
        "instantiates and calls class"
        return cls(**kwa)(data)

    def _precision(self, data:np.ndarray, _:np.ndarray, precision:Optional[float]) -> float:
        return self.getprecision(precision, data)

    def _deltas(self, data : np.ndarray) -> np.ndarray:
        "all deltas"
        raise NotImplementedError()

    def _threshold(self, data:np.ndarray, deltas:np.ndarray, precision:float) -> np.ndarray:
        raise NotImplementedError()

class MedianThreshold:
    "A threshold relying on the deltas"
    percentile = 75.
    distance   = 2.
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
    shape      = 'square'
    truncate   = 4
    confidence = MedianThreshold() # type: Union[None, float, MedianThreshold]
    @initdefaults(frozenset(locals()))
    def __init__(self, **kwa):
        super().__init__(**kwa)
        self._kernel = None # type: Optional[Tuple[Tuple[int, int, str], np.ndarray]]

    def _precision(self,
                   data     :np.ndarray,
                   deltas   :np.ndarray,
                   precision:Optional[float]
                  ) -> float:
        if self.precision == 'deltas':
            return np.median(np.abs(deltas-np.median(deltas)))
        return self.getprecision(precision, data)

    def _deltas(self, data : np.ndarray) -> np.ndarray:
        "all deltas"
        window = self.window
        if self._kernel is None or self._kernel[0] != (window, self.truncate, self.shape):
            if self.shape == 'square':
                kern   = np.ones((window*2,), dtype = 'f4')
                kern[-window:] = -1.
                kern  /= self.window
            elif self.shape == 'gaussian':
                kern  = np.linspace(-self.truncate, self.truncate,
                                    window*self.truncate*2+1, dtype = 'f4')
                kern *= -np.exp(-kern**2/2.)
                kern /= abs(kern[:len(kern)//2+1].sum())
            else:
                raise KeyError(self.shape+' is unknown in DerivateSplitDetector')
            self._kernel = (window, self.truncate, self.shape), kern
        else:
            kern = self._kernel[1]
        delta = correlate1d(data, kern, mode = 'nearest')
        return np.abs(delta)

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
