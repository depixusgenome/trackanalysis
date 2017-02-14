#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Cycle alignment: define an absolute zero common to all cycles"
from   typing import (Union, Optional, # pylint: disable=unused-import
                      Sequence, Iterable, Iterator, cast)
from   enum   import Enum
import numpy  as     np

from   signalfilter.convolve    import KernelConvolution

class AlignmentMode(Enum):
    u"Computation modes ExtremumAlignment."
    min = 'min'
    max = 'max'

class ExtremumAlignment:
    u"""
    Functor which an array of biases computed as the extremum of provided ranges.
    Biases are furthermore centered at zero around their median

    Attributes:

    * *mode*: the extremum to use
    * *binsize*: if > 2, the extremum is computed over the median of values binned
        by *binsize*.
    """
    def __init__(self, **kwa):
        self.mode    = AlignmentMode(kwa['mode'])
        self.binsize = kwa.get('binsize', 5)

    def __get(self, elem):
        bsize  = self.binsize
        binned = elem[len(elem) % bsize:].reshape((len(elem)//bsize, bsize))
        return np.median(binned, axis = 0)

    def one(self, data) -> np.ndarray:
        u"call on one table"
        fcn = getattr(np, self.mode.value)
        return -fcn(self.__get(data) if self.binsize > 2 else data)

    def many(self, data) -> np.ndarray:
        u"call on all tables"
        itr = (self.__get(j) for j in data) if self.binsize > 2 else data
        fcn = getattr(np, self.mode.value)
        res = np.fromiter((-fcn(i) for i in itr), dtype = np.float32)
        return np.subtract(res, np.median(res), out = res)

    def __call__(self, data) -> np.ndarray:
        if isinstance(data, np.ndarray) and np.isscalar(data[0]):
            return self.one(data)
        else:
            return self.many(data)

    @classmethod
    def run(cls, data, **kwa):
        u"runs the algorithm"
        return cls(**kwa)(data)

class CorrelationAlignment:
    u"""
    Finds biases which correlate best a cycle's histogram to the histogram of
    all cycles. This repeated multiple times with the latter histogram taking
    prior biases into account.

    Biases are furthermore centered at zero around their median

    Attributes:

    * *oversampling*: the amount by which histograms are oversampled. This is
        the computation's precision
    * *maxcorr*: max amount by which a cycle may be translated.
    * *nrepeats*: the number of times the procedure is repeated
    * *kernel*: the smoothing kernel to use on the data
    """
    oversampling = 5
    maxcorr      = 4
    nrepeats     = 6
    kernel       = KernelConvolution() # type: Optional[KernelConvolution]
    def __init__(self, **kwa):
        get               = lambda x: kwa.get(x, getattr(self.__class__, x))
        self.oversampling = get("oversampling")
        self.maxcorr      = get("maxcorr")
        self.nrepeats     = get("nrepeats")
        self.kernel       = kwa.get("kernel", KernelConvolution(**kwa))

    @property
    def exact_oversampling(self) -> float:
        u"The exact oversampling used: int(oversampling)//2 * 2 +1"
        return (int(self.oversampling)//2) * 2 + 1

    def __call__(self, data: Iterable[np.ndarray], **kwa) -> np.ndarray:
        if isinstance(data, Iterator):
            data = tuple(data)
        data    = cast(Sequence[np.ndarray], data)

        get     = lambda x: kwa.get(x, getattr(self, x))
        osamp   = (int(get('oversampling'))//2) * 2 + 1
        maxcorr = get('maxcorr')*osamp

        kern  = get('kernel')(oversampling = osamp, range = 'same')
        ref   = np.empty((max(len(i) for i in data)*osamp+maxcorr*2,), dtype = 'f4')
        hists = []

        cur   = ref[:-2*maxcorr]
        for rng in data:
            cur.fill(0.)
            cur[osamp//2:len(rng)*osamp:osamp] = rng
            hists.append(kern(cur))

        bias = np.full((len(hists),), maxcorr+osamp//2, dtype = np.int32)
        for _ in range(get('nrepeats')):
            ref.fill(0.)
            for start, hist in zip(bias, hists):
                ref[start:start+len(hist)] += hist

            bias  = np.fromiter((np.argmax(np.correlate(ref, hist)) for hist in hists),
                                dtype = np.float32, count = len(hists))
            bias += maxcorr+osamp//2-(bias.max()+bias.min())//2

        ref = bias/osamp
        return np.subtract(ref, np.median(ref), out = ref)

    @classmethod
    def run(cls, data: Iterable[np.ndarray], **kwa):
        u"runs the algorithm"
        return cls()(data, **kwa)

Alignment = Union[ExtremumAlignment, CorrelationAlignment]
