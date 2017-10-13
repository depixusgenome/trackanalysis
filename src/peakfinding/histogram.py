#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Creates a histogram from available events"
from    typing import (NamedTuple, Optional, Iterator,
                       Iterable, Union, Sequence, Callable, Tuple, cast)
from    enum   import Enum
import  itertools

from sklearn.mixture            import BayesianGaussianMixture
import  numpy  as     np
from    numpy.lib.stride_tricks import as_strided
from    scipy.signal            import find_peaks_cwt

from    utils                   import (kwargsdefaults, initdefaults,
                                        NoArgs, asdataarrays, EVENTS_DTYPE)
from    utils.logconfig         import getLogger
from    signalfilter            import PrecisionAlg
from    signalfilter.convolve   import KernelConvolution

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
            events = asdataarrays(aevents)
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

    def variablekernelsize(self, peaks) -> HistogramData:
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
        items   = (np.int32(np.rint(i)) for i in zmeas)  # type: ignore
        weight  = self.__weights(self.weight,   events)

        if not separate:
            items = iter((np.concatenate(tuple(items)),))
            if isinstance(weight, np.ndarray):
                weight = iter((np.concatenate(tuple(weight)),))

        yield (minv, bwidth)
        yield from self.__generate(lenv, kern, items, weight)

class FitMode(Enum):
    "Fit mode for sub-pixel peak finding"
    quadratic = 'quadratic'
    gaussian  = 'gaussian'

class SubPixelPeakPosition:
    """
    Refines the peak position using a quadratic fit
    """
    fitwidth: Optional[int] = 1
    fitcount                = 2
    fitmode                 = FitMode.quadratic
    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        pass

    def __setstate__(self, kwa):
        self.__init__(**kwa)

    def __call__(self,
                 hist :Sequence[float],
                 ainds:Union[int, Sequence[int]],
                 bias :float = 0.,
                 rho  :float = 1.):
        if self.fitwidth is None or self.fitwidth < 1:
            return ainds

        if self.fitmode is FitMode.quadratic:
            def _fitfcn(i, j, k):
                if i+2 < j:
                    fit = np.polyfit(range(i,j), hist[i:j], 2)
                    if fit[0] < 0.:
                        return -fit[1]/fit[0]*.5
                return k
            fitfcn = _fitfcn
        else:
            fitfcn = lambda i, j, _: np.average(range(i,j), weights = hist[i:j])

        inds = (ainds,) if np.isscalar(ainds) else ainds
        for _ in range(self.fitcount):
            rngs = ((max(0,         i-self.fitwidth),
                     min(len(hist), i+self.fitwidth+1),
                     i) for i in cast(Iterable, inds))

            vals = np.array([fitfcn(*i) for i in rngs], dtype = 'f4')
            inds = np.int32(np.rint(vals))      # type: ignore
        return (vals[0] if np.isscalar(ainds) else vals) * rho + bias

class CWTPeakFinder:
    "Finds peaks using scipy's find_peaks_cwt. See the latter's documentation"
    subpixel                               = SubPixelPeakPosition()
    widths:        Sequence[int]           = np.arange(5, 11)
    wavelet:       Optional[Callable]      = None
    max_distances: Optional[Sequence[int]] = None
    gap_tresh:     Optional[float]         = None
    min_length:    Optional[int]           = None
    min_snr                                = 1.
    noise_perc                             = 10.
    @initdefaults(frozenset(locals()), subpixel = 'update')
    def __init__(self, **_):
        pass

    def __call__(self, hist: np.ndarray, bias:float = 0., slope:float = 1.):
        vals = find_peaks_cwt(hist, self.widths, self.wavelet, self.max_distances,
                              self.gap_tresh, self.min_length, self.min_snr,
                              self.noise_perc)
        if self.subpixel:
            vals = self.subpixel(hist, vals)

        return np.asarray(vals) * slope + bias

class ZeroCrossingPeakFinder:
    """
    Finds peaks with a minimum *half*width and threshold
    """
    subpixel         = SubPixelPeakPosition()
    peakwidth        = 1
    threshold: float = getattr(np.finfo('f4'), 'resolution')
    @initdefaults(frozenset(locals()), subpixel = 'update')
    def __init__(self, **_):
        pass

    def __call__(self, hist: np.ndarray, bias:float = 0., slope:float = 1.):
        roll                 = np.pad(hist, self.peakwidth, 'edge')
        roll[np.isnan(roll)] = -np.inf

        roll = as_strided(roll,
                          shape    = (len(hist), 2*self.peakwidth+1),
                          strides  = (hist.strides[0],)*2)

        maxes = np.apply_along_axis(np.argmax, 1, roll) == self.peakwidth
        inds  = np.where(maxes)[0]
        inds  = inds[hist[inds] > self.threshold]

        if self.subpixel:
            inds = self.subpixel(hist, inds)
        return inds * slope + bias

class GroupByPeak:
    """
    Groups events by peak position.

    Attributes:

        * *mincount:* Peaks with fewer events are discarded.
        * *window:*   The maximum distance of an event to the peak position, in
        units of precision.
    """
    window       = 3
    mincount     = 5
    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        pass

    def _bins(self, peaks:np.ndarray, precision):
        window        = self.window*(1. if precision is None else precision)
        bins          = (np.repeat(peaks, 2).reshape((len(peaks), 2))
                         + [-window, window]).ravel()
        diff          = bins[1:-1].reshape((len(peaks)-1,2))
        div           = np.where(np.diff(diff, 1) < 0)[0]
        bins[2*div+1] = np.mean(diff[div], 1)
        bins          = np.delete(bins, 2*div+2)

        inds          = np.full((len(bins)+1,), len(peaks), dtype = 'i4')
        inds[np.searchsorted(bins, peaks)] = np.arange(len(peaks))
        return bins, inds

    @staticmethod
    def _counts(elems, bins, inds):
        tags = inds[np.digitize(np.concatenate(elems), bins)]
        cnts = np.bincount(tags)

        # inds[0] is for underflows: one of the ids to discard
        # if cnt has anything to discard, it has a size == ids[0]
        if len(cnts) == inds[0]+1:
            cnts[-1] = 0 # discard counts for events outside peak windows
        return tags, cnts

    @staticmethod
    def _grouped(elems, ids, bad):
        ids[np.in1d(ids, bad)] = np.iinfo('i4').max

        sizes  = np.insert(np.cumsum([len(i) for i in elems]), 0, 0)
        sizes  = as_strided(sizes,
                            shape   = (len(sizes)-1, 2),
                            strides = (sizes.strides[0],)*2)
        ret    = np.empty((len(sizes),), dtype = 'O')
        ret[:] = [ids[i:j] for i, j in sizes]
        return ret

    def __call__(self, peaks, elems, precision = None):
        bins, inds = self._bins(peaks, precision)
        tags, cnts = self._counts(elems, bins, inds)
        return self._grouped(elems, tags, np.where(cnts < self.mincount)[0])

class GroupByPeakAndBase(GroupByPeak):
    """
    Groups events by peak position, making sure the baseline peak is kept

    Attributes:

        * *baserange:* the range starting from the very left where the baseline
        peak should be, in µm.
    """
    baserange = .1
    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        super().__init__(**_)

    def _counts(self, elems, bins, inds):
        tags, cnts = super()._counts(elems, bins, inds)
        if len(cnts) < inds[0]+1:
            cnts = np.append(cnts, -1)
        imax       = max(inds[1:np.searchsorted(bins, bins[0]+self.baserange)+1],
                         default = -1, key = cnts.__getitem__)
        if imax >= 0:
            imin       = min(i for i in range(imax+1) if cnts[i] == cnts[imax])
            cnts[imin] = self.mincount # make sure peak is accepted
        return tags, cnts

class ByZeroCrossing:
    """
    Finds peaks with a minimum *half*width and threshold
    """
    subpixel         = SubPixelPeakPosition()
    peakwidth        = 1
    threshold: float = getattr(np.finfo('f4'), 'resolution')
    finder           = ZeroCrossingPeakFinder()
    grouper          = GroupByPeakAndBase()
    @initdefaults(frozenset(locals()), subpixel = 'update')
    def __init__(self, **_):
        pass

    def find(self, *args, **kwa):
        'find peaks'
        return self.finder(*args,**kwa)

    def group(self, *args, **kwa):
        'group events'
        return self.grouper(*args, **kwa)

class ByGaussianMix:
    '''
    finds peaks and groups events
    '''
    max_iter  = 10000
    cov_type  = 'tied'
    peakwidth = 1
    dpgmm     = BayesianGaussianMixture()
    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        pass

    def find(self,hist: np.array, bias:float = 0., slope:float = 1.):
        'find peaks'
        cov        = np.array([[self.peakwidth]])
        ncmps      = max(int((max(hist)-min(hist))/self.peakwidth),1) # find better, smaller
        # LOGS.info(f"cov={cov}")
        # LOGS.info(f"ncmps={ncmps}")
        kwa        = {'n_components'     : ncmps,
                      'covariance_prior' : cov,
                      'covariance_type'  : self.cov_type,
                      'max_iter'         : self.max_iter}
        self.dpgmm = BayesianGaussianMixture(**kwa)
        self.dpgmm.fit(np.matrix(hist).T)
        pos        = self.dpgmm.means_[self.dpgmm.weights_>0.01][:,0]
        return pos * slope + bias

    def group(self, pos,*_1,**_2):
        'group events'
        return self.dpgmm.predict(pos)

PeakFinder = Union[ByZeroCrossing, ByGaussianMix]
