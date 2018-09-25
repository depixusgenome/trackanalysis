#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Creates a histogram from available events"
import itertools
from   typing                import (Callable, Iterable, Iterator, NamedTuple,
                                     Optional, Sequence, Tuple, Union)

import numpy                 as     np
from   scipy.interpolate     import interp1d

from   signalfilter          import PrecisionAlg
from   signalfilter.convolve import KernelConvolution
from   utils                 import (EVENTS_DTYPE, NoArgs, asdataarrays,
                                     initdefaults, asobjarray, kwargsdefaults)
from   utils.logconfig       import getLogger


LOGS       = getLogger(__name__)

HistInputs = Union[Iterable[Iterable[float]],
                   Iterable[Iterable[np.ndarray]],
                   Iterable[float]]
BiasType   = Union[None, float, np.ndarray]

class HistogramData(NamedTuple): # pylint: disable=missing-docstring
    histogram:  np.ndarray
    minvalue:   float
    binwidth:   float

class Histogram(PrecisionAlg):
    """
    Creates a gaussian smeared histogram of events.

    Attributes are:

    * *edge*: how much to add on each edge, in units of precision.
    * *oversampling*: how much to oversample the precision
    * *zmeasure*: function for computing the z-position of an event (np.nanmean per default)
    * *weight*: function for computing the weight of an event. If *None*, the weight is 1.
    * *kernel*: used for smoothing the histogram

    The functor can be called with:

    * *events*: A sequence of events, or a sequence of sequence of events. Each event is
      an array of floats.
    * *bias*: a correction factor on the z-measure to be added to each sequence of events.
      This can be a float or a sequence of floats. It must then have the same size as *events*.
    * *separate*: whether to produce one histogram for each sequence of sequences of events
      or the sum of all.

    The functor returns:
    1. a generator which returns each histogram in turn
    2. the histogram's origin
    3. the histogram's bin width
    """
    edge                                  = 0
    oversampling                          = 5
    zmeasure: Union[str, Callable, None]  = 'nanmean'
    weight:   Union[str, Callable, None]  = None
    kernel:   Optional[KernelConvolution] = KernelConvolution()
    stdpercentile                         = 75.
    stdfactor                             = 4.

    @initdefaults(frozenset(locals()), kernel = 'update')
    def __init__(self, **kwa):
        super().__init__(**kwa)

    @kwargsdefaults(asinit = False)
    def __call__(self,
                 aevents  : HistInputs,
                 bias     : BiasType = None,
                 separate : bool     = False,
                ) -> Tuple[Iterator[np.ndarray], float, float]:
        if isinstance(aevents, (list, tuple)) and all(np.isscalar(i) for i in aevents):
            events = np.array(aevents, dtype = 'f4')[None].T[None]
        elif (isinstance(aevents, np.ndarray)
              and len(aevents.shape) == 1           # type: ignore
              and str(aevents.dtype)[0] == 'f'):    # type: ignore
            events = np.array(aevents, dtype = 'f4')[None].T[None]
        else:
            events = asdataarrays(aevents) # type: ignore
            if events is None:
                return np.empty((0,), dtype = 'f4'), np.inf, 0.

            if (self.zmeasure is not None
                    and np.isscalar(next(i[0] for i in events if len(i)))):
                events = (events,)

        gen          = self.__compute(events, bias, separate)
        minv, bwidth = next(gen)
        return gen, minv, bwidth

    def projection(self, aevents : HistInputs, bias: BiasType = None, **kwa):
        "Calls itself and returns the sum of histograms + min value and bin size"
        tmp, minv, bwidth = self(aevents, bias, separate = False, **kwa)
        return HistogramData(next(tmp), minv, bwidth)

    def apply(self, minv, bwidth, lenv, arr):
        "Applies to one array"
        osamp = (int(self.oversampling)//2) * 2 + 1
        tmp   = np.int32(np.rint((arr-minv)/bwidth))
        # pylint: disable=unsubscriptable-object
        res   = np.bincount(tmp[tmp >= 0], minlength = lenv)[:lenv]
        if self.kernel is not None:
            return self.kernel(oversampling = osamp, range = 'same')(res)
        return res

    @property
    def exactoversampling(self) -> int:
        "returns the exact oversampling used"
        return (int(self.oversampling)//2) * 2 + 1

    def eventpositions(self,
                       aevents  : Union[Iterable[Iterable[float]],
                                        Iterable[Iterable[np.ndarray]]],
                       bias     : Union[None,float,np.ndarray] = None,
                       zmeasure : Union[None,type,Callable]    = NoArgs) -> np.ndarray:
        "Returns event positions as will be added to the histogram"
        events = asdataarrays(aevents)
        first  = None if events is None else next((i for i in events if len(i)), None)
        if first is None:
            return np.empty((0,), dtype = 'f4')

        assert getattr(first, 'dtype', 'f') != EVENTS_DTYPE
        if np.isscalar(first[0]):
            fcn = None
        else:
            fcn = self.zmeasure if zmeasure is NoArgs else zmeasure
            if isinstance(fcn, str):
                fcn = getattr(np, fcn)
        return self.__eventpositions(events, bias, fcn)

    def positionsandprecision(self, data, precision) -> Optional[Tuple[np.ndarray, float]]:
        "computes positions and the precision"
        data  = asobjarray(data)
        first = next((i for i in data if len(i)), None)
        if first is None:
            return None

        if getattr(first, 'dtype', 'f') == EVENTS_DTYPE or not np.isscalar(first[0]):
            return self.getprecision(precision, data), self.eventpositions(data)

        if precision is None:
            return data, self.precision

        return data, precision

    def kernelarray(self) -> np.ndarray:
        "the kernel used in the histogram creation"
        if self.kernel is not None:
            osamp = (int(self.oversampling)//2) * 2 + 1
            return self.kernel.kernel(oversampling = osamp, range = 'same')

        return np.array([1.], dtype = 'f4')

    @classmethod
    def run(cls, *args, **kwa):
        "runs the algorithm"
        return cls()(*args, **kwa)

    def variablekernelsize(self, # pylint: disable=too-many-locals
                           peaks) -> HistogramData:
        "computes a histogram where the kernel size may vary"
        osamp  = (int(self.oversampling)//2) * 2 + 1
        bwidth = self.getprecision(self.precision)/osamp
        minv   = min(i for i, _ in peaks) - self.edge*bwidth*osamp
        maxv   = max(i for i, _ in peaks) + self.edge*bwidth*osamp
        lenv   = int((maxv-minv)/bwidth)+1
        arr    = np.zeros((lenv,), dtype = 'f4')

        peaks  = self.__rint_peaks(peaks, minv, bwidth, lenv)
        if self.kernel is None:
            arr[peaks[:,0]] += 1
        else:
            last = -1
            for ipeak, std in sorted(peaks, key = lambda x: x[1]):
                if last != std:
                    base = self.kernel.kernel(width = std)
                    last = std
                kern = base
                imin = ipeak-kern.size//2
                imax = ipeak+kern.size//2+1

                if imin < 0:
                    kern = kern[-imin:]
                    imin = None

                if imax > lenv:
                    kern = kern[:lenv-imax]
                    imax = None

                arr[imin:imax] = kern
        return HistogramData(arr, minv, bwidth)

    def __rint_peaks(self, peaks, minv, bwidth, lenv):
        # pylint: disable=unsubscriptable-object
        peaks       = np.int32(np.rint((peaks-[minv,0])/bwidth)) # type: ignore
        peaks       = peaks[np.logical_and(peaks[:,0] >= 0, peaks[:,0] < lenv)]
        defaultstd  = np.percentile(peaks[:,1][peaks[:,1]>0], self.stdpercentile)
        peaks[:,1][peaks[:,1] <= 0] = defaultstd
        if defaultstd == 0:
            peaks[:,1] = bwidth*self.stdfactor
        return peaks

    @staticmethod
    def __eventpositions(events, bias, fcn):
        res = np.empty((len(events),), dtype = 'O')

        if fcn is None or np.isscalar(next(i[0] for i in events if len(i))):
            res[:] = [np.asarray(evts, dtype = 'f4') for evts in events]
            if bias is not None:
                res[:]  = res + np.asarray(bias, dtype = 'f4')
        else:
            if isinstance(fcn, str):
                fcn = getattr(np, fcn)
            res[:] = [np.array([fcn(i) for i in evts], dtype = 'f4')
                      for evts in events]

            if bias is not None:
                res[:] += np.asarray(bias, dtype = 'f4')
        return res

    @staticmethod
    def __weights(fcn, events):
        if isinstance(fcn, str):
            fcn = getattr(np, fcn)
        return (itertools.repeat(1., len(events)) if fcn is None                 else
                fcn                               if isinstance(fcn, np.ndarray) else
                (fcn(evts) for evts in events))

    @staticmethod
    def __generate(lenv, kern, zmeas, weights):
        for pos, weight in zip(zmeas, weights):
            if weight == 0. or len(pos) == 0:
                yield np.zeros((lenv,), dtype = 'i8')
                continue
            elif weight == 1.:
                cnt = np.bincount(pos, minlength = lenv)
            elif np.isscalar(weight):
                cnt = np.bincount(pos, minlength = lenv) * weight
            else:
                cnt = np.bincount(pos, minlength = lenv, weights = weight)
            yield kern(cnt)

    def __compute(self,
                  events   : Sequence[Sequence[np.ndarray]],
                  bias     : Union[None,float,np.ndarray],
                  separate : bool):
        osamp  = (int(self.oversampling)//2) * 2 + 1
        bwidth = self.getprecision(self.precision, events)/osamp

        zmeas  = self.__eventpositions(events, bias, self.zmeasure)
        if not any(len(i) for i in zmeas):
            yield (np.inf, 0.)
            return

        minv   = min(min(i) for i in zmeas if len(i)) - self.edge*bwidth*osamp
        maxv   = max(max(i) for i in zmeas if len(i)) + self.edge*bwidth*osamp
        lenv   = int((maxv-minv)/bwidth)+1

        if self.kernel is not None:
            kern = self.kernel(oversampling = osamp, range = 'same')
        else:
            kern = lambda x: x

        zmeas  -= minv
        zmeas  /= bwidth
        items: Iterator = (np.int32(np.rint(i)) for i in zmeas)  # type: ignore
        weight  = self.__weights(self.weight,   events)

        if not separate:
            items = iter((np.concatenate(tuple(items)),))
            if isinstance(weight, np.ndarray):
                weight = iter((np.concatenate(tuple(weight)),))

        yield (minv, bwidth)
        yield from self.__generate(lenv, kern, items, weight)

def interpolator(xaxis, yaxis = None, miny = 1e-3, **kwa):
    "interpolates histograms"
    if hasattr(xaxis, 'histogram') and yaxis is None:
        yaxis = xaxis.histogram

    if hasattr(xaxis, 'binwidth'):
        xaxis = np.arange(len(yaxis), dtype = 'f4')*xaxis.binwidth+xaxis.minvalue

    yaxis = np.copy(yaxis)
    tmp   = np.isfinite(yaxis)
    yaxis = yaxis[tmp]
    xaxis = xaxis[tmp]

    yaxis[yaxis < miny] = 0.

    tmp   = np.nonzero(np.abs(np.diff(yaxis)) > miny*1e-2)[0]
    good  = np.union1d(tmp, tmp+1)

    yaxis = yaxis[good]
    xaxis = xaxis[good]

    kwa.setdefault('fill_value',   np.NaN)
    kwa.setdefault('bounds_error', False)
    return interp1d(xaxis, yaxis, assume_sorted = True, **kwa)
