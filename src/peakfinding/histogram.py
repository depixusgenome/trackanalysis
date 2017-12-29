#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Creates a histogram from available events"
from    typing                  import (NamedTuple, Optional, Iterator,
                                        Iterable, Union, Sequence, Callable, Tuple, cast,
                                        Dict)
from    enum                    import Enum
import  itertools
from functools                  import partial
from sklearn.mixture            import GaussianMixture
from sklearn.cluster            import KMeans
import  numpy  as     np
from    numpy.lib.stride_tricks import as_strided
from    scipy.interpolate       import interp1d
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

    # Attributes

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

    # Attributes

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
    finder           = ZeroCrossingPeakFinder()
    grouper          = GroupByPeakAndBase()
    @initdefaults(frozenset(locals()), subpixel = 'update')
    def __init__(self, **kwa):
        pass
    def __call__(self,**kwa):
        hist  = kwa.get("hist",(np.array([]),0,1))
        peaks = self.finder(*hist)
        ids   = self.grouper(peaks     = peaks,
                             elems     = kwa.get("pos"),
                             precision = kwa.get("precision",None))
        return peaks, ids

class ByGaussianMix:
    '''
    finds peaks and groups events using Gaussian mixture
    the number of components is estimated using BIC criteria
    '''
    max_iter        = 10000
    cov_type        = 'full'
    peakwidth       = 1
    crit            = 'bic'
    mincount        = 5
    varcmpnts       = 0.2

    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        pass

    def __call__(self,**kwa):
        pos            = kwa.get("pos",None)
        self.peakwidth = kwa.get("precision",1)
        hist, bias, slope   = kwa.get("hist",(0,0,1))
        return self.find(pos, hist, bias, slope)

    def find(self,pos: np.ndarray, hist, bias:float = 0., slope:float = 1.):
        'find peaks'
        events   = np.hstack(pos)
        zcnpeaks = len(ZeroCrossingPeakFinder()(hist,bias, slope))
        kwargs   = {'covariance_type': self.cov_type,
                    'max_iter' : self.max_iter}
        # needs better estimation
        gmm      = self.__fit(events.reshape(-1,1),
                              max(int(zcnpeaks*(1+self.varcmpnts)),2),
                              max(int(zcnpeaks*(1-self.varcmpnts)),1),
                              kwargs)

        peaks    = gmm.means_.reshape(1,-1)[0] * slope + bias
        ids      = self.__strip(pos,events.reshape(-1,1),gmm)

        speaks   = sorted([(idx,val) for idx,val in enumerate(peaks)],
                          key =lambda x:x[1])

        sort     = {idy[0] :idx for idx,idy in enumerate(speaks)}
        sort[cast(int,np.iinfo("i4").max)] = cast(int,np.iinfo("i4").max)
        def sorting(idarr):
            'rename indices to match sorted peaks'
            if idarr.size>0:
                return np.array([sort[_] for _ in idarr])
            return np.array([])
        return np.sort(peaks), [sorting(idx) for idx in ids]

    def __strip(self,pos,evts,gmm):
        'removes peaks which have fewer than mincount events'
        predicts = gmm.predict(evts)
        keep     = [pkid for pkid in range(gmm.n_components) if sum(predicts==pkid)>=self.mincount]

        def assign(zpos):
            'set id'
            idx = gmm.predict(zpos)[0]
            return idx if idx in keep else np.iinfo("i4").max

        vids = np.vectorize(assign)
        return np.array([vids(zpos) if zpos.size>0 else np.array([]) for zpos in pos])

    def __fit(self,evts,maxcmpts,mincmpts,kwargs):
        '''
        runs Gaussian Mixture for different components
        returns the one which minimizes crit
        '''
        gmms = self.__run_gmms(evts,maxcmpts,mincmpts,kwargs)
        return self.__min_crit(self.crit,evts,gmms)

    @staticmethod
    def __run_gmms(evts:np.ndarray,maxncmps:int,mincmps:int,kwargs:Dict):
        gmms = [GaussianMixture(n_components = ite,**kwargs) for ite in range(mincmps,maxncmps)]
        for ite in range(maxncmps-mincmps):
            gmms[ite].fit(evts)
        return gmms

    @staticmethod
    def __min_crit(crit:str,evts:np.ndarray,gmms):
        values = [getattr(gmm,crit)(evts) for gmm in gmms]
        return gmms[np.argmin(values)]

class COVTYPE(Enum):
    'defines constraints on covariance'
    ANY  = 1
    TIED = 2

# set data as instance attribute
class ByEM:
    '''
    finds peaks and groups events using Expectation Maximization
    the number of components is estimated using BIC criteria
    tests to add:
    test params from init
    for r in param:
    try r.reshape(2,-1) (see cls.scorex)
    '''
    emiter   = 100
    tol      = 1e-2
    mincount = 5
    tol      = 1e-1 # loglikelihood tolerance
    covtype  = COVTYPE.ANY
    params  : np.ndarray
    rates   : np.ndarray

    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        pass

    def __call__(self,**kwa):
        events = kwa.get("events",None) # np.ndarray per cycles
        _, bias, slope  = kwa.get("hist",(0,0,1))
        npeaks = len(ZeroCrossingPeakFinder()(*kwa.get("hist",(0,0,1))))
        return self.find(events, bias, slope, npeaks)

    def find(self, events, bias, slope, npeaks:int):
        'find peaks'
        data   = np.array([[np.nanmean(i),len(i)] for i in np.hstack(events)])
        params = self.fit(data,npeaks)[1]
        order  = np.argsort(params.T[0,:])
        peaks, ids = self.__strip(params[order,:],data,events)
        return peaks * slope + bias , ids

    def __strip(self, params, data, events):
        '''
        removes peaks which have fewer than mincount events
        then assigns events to most likely peaks
        '''
        predicts = np.array([np.argmax(_) for _ in self.score(data,params).T])
        lowcount = [pkid for pkid in range(params.shape[0]) if np.sum(predicts==pkid)<self.mincount]
        pos = np.array([ np.array([[np.nanmean(evt),len(evt)] for evt in cyc])
                         if cyc.size>0 else np.array([]) for cyc in events])

        ids = np.array([self.__predict(zpos,params) for zpos in pos])
        ids[np.isin(ids,lowcount)]=np.iinfo("i4").max # unassigned events
        return params.T[0,:], ids

    # to test
    def nparams(self,params):
        'returns the number of estimated params'
        if self.covtype is COVTYPE.TIED:
            dim = params.shape[1]//2-1
            return params.size-dim*(params.shape[0]-1)
        return params.size

    @classmethod
    def __predict(cls, data:np.ndarray, params:np.ndarray):
        if data.size==0:
            return np.array([])
        ids = np.array([np.argmax(_) for _ in cls.score(data,params).T])
        return ids

    # to pytest
    @staticmethod
    def init(data:np.ndarray,npeaks=1)->np.ndarray:
        'init using KMeans on spatial data'
        kmean   = KMeans(npeaks)
        kmean.fit(data[:,:-1])
        predict = kmean.predict(data[:,:-1])

        clas    = {idx:np.array([data[_1] for _1,_2 in enumerate(predict) if _2==idx])
                   for idx in range(npeaks)}

        params  = [[(np.nanmean(clas[idx][:,:-1],axis=0),np.nanstd(clas[idx][:,:-1],axis=0)),
                    (0,np.nanstd(clas[idx][:,-1]))] for idx in range(npeaks)]
        rates   = 1/npeaks*np.ones((npeaks,1))
        return rates, params

    @staticmethod
    def __normlpdf(loc, scale, pos):
        'log pdf of Gaussian dist'
        return -np.log(scale)-0.5*((pos-loc)/scale)**2

    @staticmethod
    def __normpdf(loc, scale, pos):
        'pdf of Gaussian dist'
        return np.exp(-0.5*((pos-loc)/scale)**2)/(np.sqrt(2*np.pi)*scale)

    @staticmethod
    def __explpdf(loc, scale, pos):
        'log pdf of exponential dist'
        return -np.log(scale)+(loc-pos)/scale

    @staticmethod
    def __exppdf(loc, scale, pos):
        'log pdf of exponential dist'
        return 0 if loc>pos else float(np.exp((loc-pos)/scale)/scale)

    @classmethod
    def pdf(cls,*args): #args:np.ndarray)->float:
        '''
        args : np.array([[xloc,xscale,xpos],
                         [yloc,yscale,ypos],
                         [zloc,zscale,zpos],
                         [tloc,tscale,tpos]])
        '''
        # before
        #return np.prod([cls.__normpdf(*par) for par in args[:-1]])*cls.__exppdf(*args[-1])
        param, datum=args[0]
        return cls.mvnormpdf(*param[0],datum[:-1])*cls.__exppdf(*param[1],datum[-1])

    # @classmethod
    # def score(cls,data:np.ndarray,params)->np.ndarray:# to fix
    #     'return the score[i,j] array corresponding to pdf(Xj|Zi, theta)'
    #     mid      = params.shape[1]//2
    #     locscale = np.array([list(zip(r[:mid],r[mid:])) for r in params])
    #     pdf      = map(lambda x:cls.pdf(np.hstack([x[0],x[1].reshape(-1,1)])),
    #                    itertools.product(locscale,data))

    #     return np.array(list(pdf)).reshape(len(params),-1)

    # pytest
    @classmethod
    def mvnormlpdf(cls,mean,cov,pos):
        'proportional to log normal pdf of multivariate distribution'
        cent = pos-mean
        return -0.5*(np.log(np.linalg.det(cov))-cent.T*np.linalg.inv(cov)*cent)

    # pytest
    @classmethod
    def mvnormpdf(cls,mean,cov,pos):
        'proportional to normal pdf of multivariate distribution'
        if len(pos)==1:
            return float(cls.__normpdf(mean, cov, pos))
        cent   = np.matrix(pos-mean)
        return np.exp(-0.5*float(cent*np.linalg.inv(cov)*cent.T))/\
            np.sqrt(float(np.linalg.det(cov)))

    @classmethod
    def score(cls,data:np.ndarray,params)->np.ndarray: # to fix
        'return the score[i,j] array corresponding to pdf(Xj|Zi, theta)'
        pdf = map(cls.pdf,itertools.product(params,data))
        return np.array(list(pdf)).reshape(len(params),-1)

    def emstep(self,data:np.ndarray,rates:np.ndarray,params:np.ndarray):
        'Expectation then Maximization steps of EM'
        score = self.score(data,params)
        pz_x  = score*rates # P(Z,X|theta) prop P(Z|X,theta)
        pz_x  = np.array(pz_x)/np.sum(pz_x,axis=0) # renorm over Z
        rates, params = self.maximization(pz_x,data)
        # if self.covtype is COVTYPE.TIED:# to fix
        #     mid = params.shape[1]//2
        #     params[:,mid:-1]=np.mean(params[:,mid:-1],axis=0)
        return self.score(data,params), rates, params

    # to pytest, to extend to x,y,z
    # @classmethod
    # def maximization(cls,pz_x:np.ndarray,data:np.ndarray,params:np.ndarray):
    #     'returns the next set of parameters'
    #     nrates    = np.mean(pz_x,axis=1).reshape(-1,1)
    #     # spatial params on data[:,:-1]
    #     nmeans    = np.array(np.matrix(pz_x)*data[:,:-1])
    #     nmeans   /= np.sum(pz_x,axis=1).reshape(-1,1)

    #     center    = (data[:,:-1].T - nmeans)**2 # each row corresponds to a param
    #     nscales   = np.array([np.matrix(pz_x[idx,:])*r.reshape(-1,1)
    #                           for idx,r in enumerate(center)]).reshape(-1,1)

    #     nscales  /= np.sum(pz_x,axis=1).reshape(-1,1) # estimation of variance! not std
    #     nscales   = np.sqrt(nscales)

    #     # temporal params on data[:,-1]
    #     tmeans    = np.array([0]*params.shape[0]).reshape(-1,1)

    #     tscales   = np.array(np.matrix(pz_x)*data[:,-1].reshape(-1,1))
    #     tscales  /= np.sum(pz_x,axis=1).reshape(-1,1)
    #     return nrates,np.hstack([nmeans,tmeans,nscales,tscales])

    @classmethod
    def __maximizeparam(cls,data,proba):
        'maximizes a parameter'
        nmeans = np.array(np.matrix(proba)*data[:,:-1]).ravel()
        ncov   = np.cov(data[:,:-1].T,aweights = proba ,ddof=0)
        # temporal params on data[:,-1], tmean is 0
        tscale = np.sum(proba*data[:,-1])

        return [(nmeans,ncov),(0.,tscale)]

    # to pytest, to extend to x,y,z
    @classmethod
    def maximization(cls,pz_x:np.ndarray,data:np.ndarray):
        'returns the next set of parameters'

        nrates   = np.mean(pz_x,axis=1).reshape(-1,1)

        npz_x    = pz_x/np.sum(pz_x,axis=1).reshape(-1,1)
        maximize = partial(cls.__maximizeparam,data)
        return nrates, list(map(maximize,npz_x)) # type: ignore

    # pytest
    @classmethod
    def assign(cls,score:np.ndarray)->Dict[int,Tuple[int, ...]]:
        'to each event (row in data) assigns a peak (row in params)'
        # Gaussian distribution for position, exponential for duration
        # score[j,i] = pdf(Xi|Zj, theta)
        assigned = sorted([(np.argmax(row),idx) for idx,row in enumerate(score.T)])
        out : Dict[int,Tuple[int, ...]] = {_:tuple() for _ in range(score.shape[0])}
        out.update({key: tuple(i[1] for i in grp)
                    for key,grp in itertools.groupby(assigned,lambda x:x[0])})
        return out

    def bic(self,score:np.ndarray,rates:np.ndarray,params:np.ndarray)->float:
        'returns bic value'
        llikeli = self.llikelihood(score,rates)
        # number of params rates + params assuming tmean is 0
        return -2*llikeli + self.nparams(params) *np.log(0.5*score.shape[1]/np.pi)

    def aic(self,score:np.ndarray,rates:np.ndarray,params:np.ndarray)->float:
        'returns bic value'
        return 2*self.nparams(params) -2*self.llikelihood(score,rates)

    @classmethod
    def llikelihood(cls,score:np.ndarray,rates:np.ndarray)->float:
        'returns loglikelihood'
        return np.sum(np.log(np.sum(rates*score,axis=0)))

    # to pytest
    def __fit(self,
              data,
              rates,
              params,
              prevll:Optional[float] = None):
        prevll = self.llikelihood(self.score(data,params),rates) if prevll is None else prevll
        for _ in range(self.emiter):
            score, rates, params = self.emstep(data,rates,params)
            llikelihood  = self.llikelihood(score,rates)
            if abs(llikelihood-prevll) > self.tol:
                prevll = llikelihood
            else:
                break
            if any(self.assign(score).values())<self.mincount:
                break
        return rates,params

    def fit(self,data:np.ndarray,npeaks:int):
        'iterate EM to fit a given number of peaks'
        rates,params = self.init(data,npeaks)
        return self.__fit(data,rates,params,prevll=None)

PeakFinder = Union[ByZeroCrossing, ByGaussianMix, ByEM]
