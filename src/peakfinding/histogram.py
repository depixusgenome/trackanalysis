#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Creates a histogram from available events"
from    typing import (Optional, Iterator, # pylint: disable=unused-import
                       Iterable, Union, Sequence, Callable, Tuple, cast)
from    enum   import Enum
import  itertools
import  numpy  as     np
from    numpy.lib.stride_tricks import as_strided
from    scipy.signal            import find_peaks_cwt

from    utils                   import kwargsdefaults, initdefaults
from    signalfilter.convolve   import KernelConvolution # pylint: disable=unused-import

class Histogram:
    u"""
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
    * *delta*: a correction factor on the z-measure to be added to each sequence of events.
      This can be a float or a sequence of floats. It must then have the same size as *events*.
    * *separate*: whether to produce one histogram for each sequence of sequences of events
      or the sum of all.

    The functor returns:
    1. a generator which returns each histogram in turn
    2. the histogram's origin
    3. the histogram's bin width
    """
    edge         = 0
    oversampling = 5
    precision    = None                 # type: Optional[float]
    zmeasure     = np.nanmean           # type: Optional[Callable]
    weight       = None                 # type: Optional[Callable]
    kernel       = KernelConvolution()  # type: Optional[KernelConvolution]

    @initdefaults('edge', 'oversampling', 'precision', 'zmeasure', 'weight')
    def __init__(self, **kwa):
        self.kernel = kwa.get("kernel", KernelConvolution(**kwa))

    @property
    def exact_oversampling(self) -> float:
        u"The exact oversampling used: int(oversampling)//2 * 2 +1"
        return (int(self.oversampling)//2) * 2 + 1

    @property
    def binwidth(self) -> float:
        u"The width of one bin: precision / exact_oversampling"
        return self.precision / self.exact_oversampling

    @staticmethod
    def __eventpositions(events, fcn):
        if fcn is None:
            return events
        else:
            return np.array([np.fromiter((fcn(i) for i in evts),
                                         dtype = 'f4', count = len(evts))
                             for evts in events], dtype = 'O')

    def eventpositions(self,
                       events   : Iterable[Iterable[np.ndarray]],
                       zmeasure : Union[str,None,Callable] = '--none--') -> np.ndarray:
        u"Returns event positions as will be added to the histogram"
        if isinstance(events, Iterator):
            events = tuple(events)
        events = cast(Sequence[Iterable[np.ndarray]], events)

        if len(events) == 0:
            return np.empty((0,), dtype = 'f4')

        if isinstance(events[0], Iterator):
            events = tuple(tuple(evts) for evts in events)
        events = cast(Sequence[Sequence[np.ndarray]], events)

        if np.isscalar(events[0][0]):
            events = events,

        fcn = self.zmeasure if zmeasure is '--none--' else zmeasure
        return self.__eventpositions(events, fcn)

    @staticmethod
    def __weights(fcn, events):
        if fcn is None:
            return itertools.repeat(1., len(events))
        else:
            return (fcn(evts) for evts in events)

    @staticmethod
    def __generate(lenv, kern, zmeas, weights):
        for pos, weight in zip(zmeas, weights):
            if np.isscalar(weight):
                cnt = np.bincount(pos, minlength = lenv) * weight
            else:
                cnt = np.bincount(pos, minlength = lenv, weights = weight)
            yield kern(cnt)

    @kwargsdefaults
    def __compute(self,
                  events   : Sequence[Sequence[np.ndarray]],
                  delta    : Union[None,float,np.ndarray],
                  separate : bool):
        osamp  = (int(self.oversampling)//2) * 2 + 1
        bwidth = self.precision/osamp

        if self.zmeasure is None:
            minv = np.min(events)
            maxv = np.max(events)
        else:
            minv = min(np.nanmin(evt) for evts in events for evt in evts)
            maxv = max(np.nanmax(evt) for evts in events for evt in evts)

        minv -= self.edge*bwidth*osamp
        maxv += self.edge*bwidth*osamp
        lenv  = int((maxv-minv)/bwidth)+1

        if self.kernel is not None:
            kern = self.kernel(oversampling = osamp, range = 'same')
        else:
            kern = lambda x: x

        zmeas  = self.__eventpositions(events, self.zmeasure)
        if delta is not None:
            zmeas += delta
        zmeas  -= minv
        zmeas  /= bwidth
        items   = (np.int32(i) for i in zmeas)      # type: ignore

        weight  = self.__weights  (self.weight,   events)

        if not separate:
            items = iter((np.concatenate(tuple(items)),))
            if isinstance(weight, np.ndarray):
                weight = weight.ravel()[np.newaxis] # pylint: disable=no-member

        yield (minv, bwidth)
        yield from self.__generate(lenv, kern, items, weight)

    def __call__(self,
                 events   : Iterable[Iterable[np.ndarray]],
                 delta    : Union[None,float,np.ndarray] = None,
                 separate : bool                         = False,
                 **kwa) -> Tuple[Iterator[np.ndarray], float, float]:
        if isinstance(events, Iterator):
            events = tuple(events)
        events = cast(Sequence[Iterable[np.ndarray]], events)

        if len(events) == 0:
            return np.empty((0,), dtype = 'f4'), np.inf, 0.

        if isinstance(events[0], Iterator):
            events = tuple(tuple(evts) for evts in events)
        events = cast(Sequence[Sequence[np.ndarray]], events)

        if np.isscalar(events[0][0]):
            events = events,

        gen          = self.__compute(events, delta, separate, **kwa)
        minv, bwidth = next(gen)
        return gen, minv, bwidth

    @classmethod
    def run(cls, *args, **kwa):
        u"runs the algorithm"
        return cls()(*args, **kwa)

class FitMode(Enum):
    u"Fit mode for sub-pixel peak finding"
    quadratic = 'quadratic'
    gaussian  = 'gaussian'

class _m_SubPixelPeakMixin: # pylint: disable=invalid-name
    u"""
    Refines the peak position using a quadratic fit
    """
    fitwidth = 1 # type: Optional[int]
    fitcount = 2
    fitmode  = FitMode.quadratic
    @initdefaults('fitwidth', 'fitcount', 'fitmode')
    def __init__(self, **_):
        pass

    def _inds(self, hist):
        raise NotImplementedError()

    def __call__(self, hist, bias:float, rho: float):
        inds = self._inds(hist)
        if self.fitwidth is None or self.fitwidth < 1:
            return inds

        if self.fitmode is FitMode.quadratic:
            def _fitfcn(i, j):
                fit = np.polyfit(range(i,j), hist[i:j], 2)
                return (False, 0.) if fit[0] >= 0. else (True, -fit[1]/fit[0]*.5)
            fitfcn = _fitfcn
        else:
            fitfcn = lambda i, j: (True, np.average(range(i,j), weights = hist[i:j]))

        for _ in range(self.fitcount):
            rngs = tuple((max(0,         i-self.fitwidth),
                          min(len(hist), i+self.fitwidth+1)
                         ) for i in inds)

            fits = tuple(fitfcn(i, j) for i, j in rngs if i+2 < j)
            vals = np.array([fit[1] for fit in fits if fit[0]])
            inds = np.int32(vals+.5) # type: ignore
        return vals * rho + bias

class CWTPeakFinder(_m_SubPixelPeakMixin):
    u"Finds peaks using scipy's find_peaks_cwt. See the latter's documentation"
    widths        = np.arange(5, 11) # type: Sequence[int]
    wavelet       = None             # type: Optional[Callable]
    max_distances = None             # type: Optional[Sequence[int]]
    gap_tresh     = None             # type: Optional[float]
    min_length    = None             # type: Optional[int]
    min_snr       = 1.
    noise_perc    = 10.
    @initdefaults('widths', 'wavelet', 'max_distances', 'gap_tresh',
                  'min_length', 'min_snr', 'noise_perc')
    def __init__(self, **_):
        super().__init__(**_)

    def _inds(self, hist):
        vals = find_peaks_cwt(hist, self.widths, self.wavelet, self.max_distances,
                              self.gap_tresh, self.min_length, self.min_snr,
                              self.noise_perc)
        return np.array(vals)

class ZeroCrossingPeakFinder(_m_SubPixelPeakMixin):
    u"""
    Finds peaks with a minimum *half*width and threshold
    """
    peakwidth = 1
    threshold = getattr(np.finfo('f4'), 'resolution') # type: float
    @initdefaults('peakwidth', 'threshold')
    def __init__(self, **_):
        super().__init__(**_)

    def _inds(self, hist):
        roll                 = np.pad(hist, self.peakwidth, 'edge')
        roll[np.isnan(roll)] = -np.inf

        roll = as_strided(roll,
                          shape    = (len(hist), 2*self.peakwidth+1),
                          strides  = (hist.strides[0],)*2)

        maxes = np.apply_along_axis(np.argmax, 1, roll) == self.peakwidth
        inds  = np.where(maxes)[0]
        return inds[hist[inds] > self.threshold]

PeakFinder = Union[CWTPeakFinder, ZeroCrossingPeakFinder]

class GroupByPeak:
    u"Groups events by peak position"
    window   = 10
    mincount = 5
    @initdefaults('window', 'mincount')
    def __init__(self, **_):
        pass

    def _bins(self, peaks:np.ndarray):
        bins      = (np.repeat(peaks, 2).reshape((len(peaks), 2))
                     + [-self.window, self.window]).ravel()
        diff      = bins[1:-1].reshape((len(peaks)-1,2))
        div       = np.where(np.diff(diff, 1) < 0)[0]
        diff[div] = np.mean(diff[div], 1)
        bins      = np.delete(bins, 2*div+1)

        inds      = np.full((len(bins)+1,), len(peaks), dtype = 'i4')
        inds[np.searchsorted(bins, peaks)] = np.arange(len(peaks))
        return bins, inds

    def __call__(self, peaks, elems):
        bins, inds = self._bins(peaks)

        ids      = inds[np.digitize(np.concatenate(elems), bins)]

        cnts     = np.bincount(ids)
        cnts[-1] = 0
        bad      = np.where(cnts < self.mincount)[0]

        ids[np.in1d(ids, bad)] = np.iinfo('i4').max

        sizes    = np.insert(np.cumsum([len(i) for i in elems]), 0, 0)
        sizes    = as_strided(sizes,
                              shape   = (len(sizes)-1, 2),
                              strides = (sizes.strides[0],)*2)
        return np.array([ids[i:j] for i, j in sizes], dtype = 'O')
