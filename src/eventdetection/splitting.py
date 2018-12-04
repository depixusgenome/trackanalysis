#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Interval detection: splitting the trace into flat events"

from    typing                      import (Optional, Tuple, Union, List,
                                            NamedTuple, cast)
from    abc                         import abstractmethod
from    enum                        import Enum

import  numpy as np
from    numpy.lib.stride_tricks     import as_strided
from    scipy.ndimage.filters       import correlate1d
from    scipy.stats.distributions   import chi2

from    utils                       import initdefaults
from    signalfilter                import PrecisionAlg

from    .threshold                  import Threshold, MedianThreshold
from    .intervalextension          import (IntervalExtension,
                                            IntervalExtensionAroundRange)

# pylint: disable=no-name-in-module,import-error,unused-import
from    ._core  import (samples as _samples,
                        DerivateSplitDetector,
                        ChiSquareSplitDetector,
                        MultiGradeSplitDetector)
norm = _samples.normal.knownsigma # pylint: disable=invalid-name

class SplitDetector(PrecisionAlg):
    """
    Splits the data into flat stretches of value.

    The child class will define how to compute the stretches. The latter can
    be extended using the *extend* field.
    """
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
            return self.extend(ends, data, prec)
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

    if *erode* is above 0, intervals of *flatness* are eroded on both sides by
    by up to *erode* unless it means discarding the maximum from that interval.
    """
    erode = 0
    @initdefaults(frozenset(locals()))
    def __init__(self, **kwa):
        super().__init__(**kwa)

    @staticmethod
    def _erode(erode, deltas, threshold):
        if erode <= 0:
            return

        above = deltas > threshold

        below = ~above
        rngs  = (np.logical_and(above[1:], below[:-1]).nonzero()[0],
                 np.logical_and(below[1:], above[:-1]).nonzero()[0])

        if len(rngs[0]) and len(rngs[1]) and rngs[0][0] > rngs[1][0]:
            rngs = rngs[0], rngs[1][1:]

        for i, j in zip(*rngs):
            if i+1 == j:
                continue

            inter = deltas[i+1:j+1]
            imax  = np.argmax(inter)
            inter[:min(erode, imax)]              = 0.
            inter[max(imax+1, len(inter)-erode):] = 0.

    def _boundaries(self,
                    data      : np.ndarray,
                    good      : np.ndarray,
                    precision : float
                   ) -> np.ndarray:
        deltas    = self._flatness(good)
        threshold = self._threshold(data, deltas, precision)
        self._erode(self.erode, deltas, threshold)
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
        precision = self.getprecision(precision, data)
        deltas   /= self._threshold(data, deltas, precision)
        if len(tmp) == len(nans):
            return deltas

        result        = np.full((len(nans),), np.NaN, dtype = 'f4')
        result[~nans] = deltas
        return result

    @abstractmethod
    def _flatness(self, data : np.ndarray) -> np.ndarray:
        "Computes a flatness characteristic on all indices"

    @abstractmethod
    def _threshold(self,
                   data      : np.ndarray,
                   deltas    : np.ndarray,
                   precision : Optional[float]
                  ) -> Optional[float]:
        "Computes a threshold on the flatness characteristic"

CONFIDENCE_TYPE = Union[None, float, Threshold] # pylint: disable=invalid-name
class PyDerivateSplitDetector(GradedSplitDetector):
    """
    Detects flat stretches of value

    Flatness is defined pointwise: 2 points are flat if close enough one to the
    other. This closeness is defined using a p-value for 2 points belonging to
    the same normal distribution with a known sigma.

    The precision is either provided or measured. In the latter case,
    the estimation used is the median-deviation of the derivative of the data.
    """
    window                      = 3
    truncate                    = 4
    shape                       = 'square'
    erode                       = 1
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
                  ) -> Optional[float]:
        if callable(self.confidence):
            return self.confidence(data, deltas, precision) # pylint: disable=not-callable

        if self.confidence is None or cast(float, self.confidence) <= 0.:
            return precision

        return norm.threshold(True, self.confidence, precision,
                              self.window, self.window)

class PyChiSquareSplitDetector(GradedSplitDetector):
    """
    Detects flat stretches of value.

    Flatness is estimated using residues of a fit to the mean of the interval.
    """
    window                                    = 4
    confidence: Union[float, None, Threshold] = .10
    @initdefaults(frozenset(locals()))
    def __init__(self, **kwa):
        super().__init__(**kwa)

    def _flatness(self, data : np.ndarray) -> np.ndarray:
        win = self.window
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
                  ) -> Optional[float]:
        if self.confidence is None:
            return precision
        if callable(self.confidence):
            return self.confidence(data, deltas, precision) # pylint: disable=not-callable
        return (precision
                * chi2.ppf(1.-cast(float,self.confidence), self.window-1)
                / self.window)

class MinMaxSplitDetector(GradedSplitDetector):
    """
    Detects flat stretches of value

    Flatness is defined pointwise: 1 point is flat versus it prior if there
    exist a window *N* such that the prior *N* are lower than this and the next
    *N-1* points by a given margin (precision).

    The precision is either provided or measured. In the latter case,
    the estimation used is the median-deviation of the derivative of the data.
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
                  ) -> Optional[float]:
        if self.confidence is None or self.confidence <= 0.:
            return precision
        return norm.threshold(True, self.confidence, precision)

class MultiGradeAggregation(Enum):
    "Possible strategies for MultiGradeSplitDetector items"
    patch   = 'patch'
    minimum = 'minimum'
    maximum = 'maximum'

    @staticmethod
    def _apply_minimum(left, right):
        np.minimum(left, right)

    @staticmethod
    def _apply_maximum(left, right):
        np.maximum(left, right)

    @staticmethod
    def _apply_patch(left, right):
        bad = left >= 1.
        bad[1:-1][np.logical_and(bad[2:], bad[:-2])] = True

        pot = np.logical_and(bad[1:-1], bad[:-2])
        pot = np.logical_and(pot, bad[2:], out = pot)
        left[1:-1][pot] = right[1:-1][pot]
        return left

    def apply(self, left, right):
        "applies the strategy"
        return getattr(self.__class__, '_apply_'+self.name)(left, right)

class MultiGradeItem(NamedTuple): # pylint: disable=missing-docstring
    detector: GradedSplitDetector
    operator: MultiGradeAggregation

class PyMultiGradeSplitDetector(SplitDetector):
    """
    Detects flat stretches of value collating multiple *flatness* indicators.

    Possible strategies for aggregation are:

    * *patch*: the final grade is the values on the left patched with values on
    the right for every index where neighbours on both sides are above
    threshold. This corrects for index cross-talking on the left grade.

    * *maximum*: the final grade is the greater value at each index: each grade
    is independant of the other and neither is too noisy. Adding their *hits*
    musn't increase the noise.

    * *minimum*: the final grade is the minor value at each index: the grades
    are noisy and thus must be in agreement.
    """
    AGG                              = MultiGradeAggregation
    ITEM                             = MultiGradeItem
    erode                            = 1
    _detectors: List[MultiGradeItem] = [ITEM(PyDerivateSplitDetector (), AGG.minimum),
                                        ITEM(PyChiSquareSplitDetector(), AGG.patch)]
    @initdefaults('detectors')
    def __init__(self, **kwa):
        super().__init__(**kwa)

    @property
    def detectors(self) -> List[MultiGradeItem]:
        "returns the list of detectors and their aggregation strategy"
        return self._detectors

    @detectors.setter
    def detectors(self, value) -> List[MultiGradeItem]:
        "returns the list of detectors and their aggregation strategy"
        self._detectors = []
        default         = self.AGG.minimum
        for i in value:
            tpe, agg = (i, default) if isinstance(i, (type, SplitDetector)) else i
            self._detectors.append(self.ITEM(tpe() if isinstance(tpe, type) else tpe,
                                             self.AGG(agg)))

        return self._detectors

    def flatness(self, data : np.ndarray, precision: float = None) -> np.ndarray:
        """
        Returns the likeliness of an interval being declared.

        Values above one define an interval boundary.
        """
        nans, good = self._init(data)
        if len(good) == 0:
            return np.full((len(data),), np.NaN, dtype = 'f4')

        precision = self.getprecision(precision, data)
        flatness  = self.__fullflatness(data, good, precision)
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
        deltas = self.__fullflatness(data, good, precision)

        # pylint: disable=protected-access
        GradedSplitDetector._erode(self.erode, deltas, 1.)
        return (deltas >= 1.).nonzero()[0]

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
        args   = data, good, precision
        deltas = self.__detectorflatness(self.detectors[0].detector, *args)
        for det, tpe in self.detectors[1:]:
            deltas = tpe.apply(deltas, self.__detectorflatness(det, *args))
        return deltas
