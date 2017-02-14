#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Creates a histogram from available events"
from    typing import (Optional, Iterator, # pylint: disable=unused-import
                       Iterable, Union, Sequence, Callable, Tuple, cast)
import  itertools
import  numpy  as     np
from    scipy.signal          import find_peaks_cwt

from    signalfilter.convolve import KernelConvolution # pylint: disable=unused-import

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
    def __init__(self, **kwa):
        get               = lambda x: kwa.get(x, getattr(self.__class__, x))
        self.edge         = get('edge')
        self.oversampling = get('oversampling')
        self.precision    = get('precision')
        self.zmeasure     = get('zmeasure')
        self.weight       = get('weight')
        self.kernel       = kwa.get("kernel", KernelConvolution(**kwa))

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

    def __compute(self,
                  events   : Sequence[Sequence[np.ndarray]],
                  delta    : Union[None,float,np.ndarray],
                  separate : bool,
                  kwa      : dict):
        get    = lambda x: kwa.get(x, getattr(self, x))
        osamp  = (int(get('oversampling'))//2) * 2 + 1
        bwidth = get('precision')/osamp

        if get('zmeasure') is None:
            minv = np.min(events)
            maxv = np.max(events)
        else:
            minv = min(np.nanmin(evt) for evts in events for evt in evts)
            maxv = max(np.nanmax(evt) for evts in events for evt in evts)

        minv -= get('edge')*bwidth*osamp
        maxv += get('edge')*bwidth*osamp
        lenv  = int((maxv-minv)/bwidth)+1

        if get('kernel') is not None:
            kern = get('kernel')(oversampling = osamp, range = 'same')
        else:
            kern = lambda x: x

        zmeas  = self.__eventpositions(events, get('zmeasure'))
        if delta is not None:
            zmeas += delta
        zmeas  -= minv
        zmeas  /= bwidth
        items   = (np.int32(i) for i in zmeas)      # type: ignore

        weight  = self.__weights  (get('weight'),   events)

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

        gen          = self.__compute(events, delta, separate, kwa)
        minv, bwidth = next(gen)
        return gen, minv, bwidth

    @classmethod
    def run(cls, *args, **kwa):
        u"runs the algorithm"
        return cls()(*args, **kwa)

class CWTPeakFinder:
    u"Finds peaks using scipy's find_peaks_cwt. See the latter's documentation"
    def __init__(self, **kwa):
        self.widths        = kwa.get("widths", [2., 5., 11.]) # type: Sequence[int]
        self.wavelet       = kwa.get("wavelet",       None)   # type: Optional[Callable]
        self.max_distances = kwa.get("max_distances", None)   # type: Optional[Sequence[int]]
        self.gap_tresh     = kwa.get("gap_tresh",     None)   # type: Optional[float]
        self.min_length    = kwa.get("min_length",    None)   # type: Optional[int]
        self.min_snr       = kwa.get("min_snr", 1.)
        self.noise_perc    = kwa.get("noise_perc",  10.)

    def __call__(self, hist, xmin:float = 0.0, width: float = 1.0):
        return find_peaks_cwt(hist, self.wavelet, self.max_distances,
                              self.gap_tresh, self.min_length, self.min_snr,
                              self.noise_perc)*width+xmin

class GroupByPeak:
    u"Groups events by peak position"
    window   = 10
    mincount = 5
    def __init__(self, **kwa):
        get           = lambda x: kwa.get(x, getattr(self.__class__, x))
        self.window   = get("window")
        self.mincount = get("mincount")

    def __call__(self, peaks, elems):
        bins  = np.copy(peaks)
        diff  = np.diff(bins)
        todiv = diff < self.window*2.
        toadd = np.nonzero(~todiv)[0]+1

        bins[todiv]  += diff[todiv]*.5
        bins[~todiv] += self.window
        bins         = np.insert(bins, toadd, peaks[toadd] - self.window)
        bins         = np.insert(bins,
                                 [0, len(bins)],
                                 (peaks[0]-self.window, peaks[-1]+self.window))
        bins        += self.window

        inds         = np.arange(len(peaks), dytpe = 'bool')
        inds         = np.insert(inds, toadd, len(peaks))
        inds         = np.insert(inds, [0, len(inds)], len(peaks))

        digitized    = inds[np.digitize(elems)]
        cnts         = np.bincount(digitized.ravel())[:-1]
        bad          = cnts[cnts < self.mincount]

        digitized[np.in1d(digitized, bad)] = len(peaks)+2
        return digitized
