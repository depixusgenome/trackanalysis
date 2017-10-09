#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Interval detection: splitting the trace into flat events"

from    typing                  import Optional, Tuple, Union, List, cast
from    abc                     import abstractmethod

import  numpy as np
from    numpy.lib.stride_tricks import as_strided
from    scipy.ndimage.filters   import correlate1d

from    utils                   import initdefaults
from    signalfilter            import samples as _samples, PrecisionAlg

from    .threshold              import Threshold, MedianThreshold
from    .intervalextension      import (IntervalExtension,
                                        IntervalExtensionAroundRange)
norm = _samples.normal.knownsigma # pylint: disable=invalid-name

class SplitDetector(PrecisionAlg):
    "Basic splitter"
    window                              = 3
    extend: Optional[IntervalExtension] = IntervalExtensionAroundRange()
    @initdefaults(frozenset(locals()))
    def __init__(self, **kwa):
        super().__init__(**kwa)

    def __call__(self,
                 data     : np.ndarray,
                 precision: Optional[float] = None
                ) -> np.ndarray:
        nans, tmp = self._init(data)
        if len(tmp) == 0:
            return np.empty((0,2), dtype = 'i4')
        prec = self.getprecision(precision, data)
        bnds = self._boundaries(data, tmp, prec)
        ends = self.__tointervals(nans, tmp, data, bnds)
        if self.extend is not None:
            return self.extend(ends, data, prec, self.window)
        return ends

    @classmethod
    def run(cls, data, **kwa):
        "instantiates and calls class"
        return cls(**kwa)(data)

    @staticmethod
    def __tointervals(nans, data, alldata, ends):
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

    @abstractmethod
    def _boundaries(self,
                    data      : np.ndarray,
                    good      : np.ndarray,
                    precision : float
                   ) -> np.ndarray:
        "returns the indexes where an interval starts or ends"

class GradedSplitDetector(SplitDetector):
    """
    Detects flat stretches of value using a single *flatness* characteristic on
    every indices versus a global threshold value.

    The intervals thus found are extended using the *extend* field.
    """
    def _boundaries(self,
                    data      : np.ndarray,
                    good      : np.ndarray,
                    precision : float
                   ) -> np.ndarray:
        deltas    = self._flatness(good)
        threshold = self._threshold(data, deltas, precision)
        return (deltas > threshold).nonzero()[0]

    def flatness(self, data : np.ndarray, precision: float = None) -> np.ndarray:
        """
        Returns the likeliness of an interval being declared.

        Values above one define an interval boundary.
        """
        nans, tmp = self._init(data)
        if len(tmp) == 0:
            return np.full((len(data),), np.NaN, dtype = 'f4')

        deltas    = self._flatness(tmp)
        deltas   /= self._threshold(data, deltas, precision)
        if len(tmp) == len(nans):
            return deltas

        result        = np.full((len(nans),), np.NaN, dtype = 'f4')
        result[~nans] = deltas
        return result

    @abstractmethod
    def _flatness(self, data : np.ndarray) -> np.ndarray:
        "Computes a flatness characteristic on all indices"
        pass

    @abstractmethod
    def _threshold(self,
                   data      : np.ndarray,
                   deltas    : np.ndarray,
                   precision : Optional[float]
                  ) -> float:
        "Computes a threshold on the flatness characteristic"
        pass

CONFIDENCE_TYPE = Union[None, float, Threshold]
class DerivateSplitDetector(GradedSplitDetector):
    """
    Detects flat stretches of value

    Flatness is defined pointwise: 2 points are flat if close enough one to the
    other. This closeness is defined using a p-value for 2 points belonging to
    the same normal distribution with a known sigma.

    The precision is either provided or measured. In the latter case,
    the estimation used is the median-deviation of the derivate of the data.
    """
    shape                       = 'square'
    truncate                    = 4
    confidence: CONFIDENCE_TYPE = MedianThreshold()
    @initdefaults(frozenset(locals()))
    def __init__(self, **kwa):
        super().__init__(**kwa)
        self._kernel: Tuple[Tuple[int, int, str], np.ndarray] = None

    def _flatness(self, data : np.ndarray) -> np.ndarray:
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

    def _threshold(self,
                   data      : np.ndarray,
                   deltas    : np.ndarray,
                   precision : Optional[float]
                  ) -> float:
        if callable(self.confidence):
            return self.confidence(data, deltas, precision) # pylint: disable=not-callable

        if self.confidence is None or cast(float, self.confidence) <= 0.:
            return precision

        return norm.threshold(True, self.confidence, precision,
                              self.window, self.window)

class ChiSquareSplitDetector(GradedSplitDetector):
    """
    Detects flat stretches of value.

    Flatness is estimated using residues of a fit to the mean of the interval.
    """
    confidence: Threshold = MedianThreshold()
    @initdefaults(frozenset(locals()))
    def __init__(self, **kwa):
        super().__init__(**kwa)

    def _flatness(self, data : np.ndarray) -> np.ndarray:
        win = (self.window//2)*2+1
        tmp = np.concatenate([[data[0]]*(win//2), data, [data[-1]]*(win//2)])
        arr = as_strided(tmp,
                         shape   = (len(data), win),
                         strides = (data.strides[0], data.strides[0]))

        good       = np.sum(np.isfinite(arr), axis = 1) > 0
        mean       = np.full(len(data), np.NaN, dtype = 'f4')
        mean[good] = np.nansum(arr[good], axis = 1)/win
        delta      = np.sqrt(np.nansum((arr-mean[None].T)**2, axis = 1)/win)
        return delta

    def _threshold(self,
                   data      : np.ndarray,
                   deltas    : np.ndarray,
                   precision : Optional[float]
                  ) -> float:
        return self.confidence(data, deltas, precision)

class MinMaxSplitDetector(GradedSplitDetector):
    """
    Detects flat stretches of value

    Flatness is defined pointwise: 1 point is flat versus it prior if there
    exist a window *N* such that the prior *N* are lower than this and the next
    *N-1* points by a given margin (precision).

    The precision is either provided or measured. In the latter case,
    the estimation used is the median-deviation of the derivate of the data.
    """
    window                      = 5
    confidence: Optional[float] = 0.1
    @initdefaults(frozenset(locals()))
    def __init__(self, **kwa):
        super().__init__(**kwa)

    def _flatness(self, data   : np.ndarray) -> np.ndarray:
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

    def _threshold(self,
                   data      : np.ndarray,
                   _         : np.ndarray,
                   precision : Optional[float]
                  ) -> float:
        if self.confidence is None or self.confidence <= 0.:
            return precision
        return norm.threshold(True, self.confidence, precision)

class MultiGradeSplitDetector(SplitDetector):
    """
    Detects flat stretches of value collating multiple *flatness* indicators.
    """
    detectors: List[GradedSplitDetector] = [ChiSquareSplitDetector(), DerivateSplitDetector()]
    @initdefaults(frozenset(locals()))
    def __init__(self, **kwa):
        super().__init__(**kwa)

    def flatness(self, data : np.ndarray, precision: float = None) -> np.ndarray:
        """
        Returns the likeliness of an interval being declared.

        Values above one define an interval boundary.
        """
        nans, good = self._init(data)
        if len(good) == 0:
            return np.full((len(data),), np.NaN, dtype = 'f4')

        flatness = self.__fullflatness(data, good, precision)
        if len(good) >= len(nans):
            return flatness

        result        = np.full(len(nans), np.NaN, dtype ='f4')
        result[~nans] = flatness
        return result

    def _boundaries(self,
                    data      : np.ndarray,
                    good      : np.ndarray,
                    precision : float
                   ) -> np.ndarray:
        return (self.__fullflatness(data, good, precision) >= 1.).nonzero()[0]

    @staticmethod
    def __detectorflatness(detector, data, good, precision):
        # pylint: disable=protected-access
        deltas  = detector._flatness(good)
        deltas /= detector._threshold(data, deltas, precision)
        return deltas

    def __fullflatness(self,
                       data      : np.ndarray,
                       good      : np.ndarray,
                       precision : Optional[float]) -> np.ndarray:
        "Computes a flatness characteristic on all indices"
        deltas = self.__detectorflatness(self.detectors[0], data, good, precision)
        for det in self.detectors[1:]:
            deltas = np.minimum(deltas, self.__detectorflatness(det, data, good, precision))
        return deltas
