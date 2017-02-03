#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Cycle alignment: define an absolute zero common to all cycles"
from   typing       import Callable, Union, Any # pylint: disable=unused-import
from   enum         import Enum
from   scipy.signal import fftconvolve
import numpy as np

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

    def __call__(self, data) -> np.ndarray:
        itr = (self.__get(j) for j in data) if self.binsize > 2 else data
        fcn = getattr(np, self.mode.value)
        res = np.fromiter((-fcn(i) for i in itr), dtype = np.float32)
        return np.subtract(res, np.median(res), out = res)

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
    * *kernel_window*: the size of the smearing kernel
    * *kernel_width*: the distribution size of the smearing kernel
    """
    def __init__(self, **kwa):
        self.oversampling  = kwa.get("oversampling",  5)
        self.maxcorr       = kwa.get("maxcorr",       4)
        self.nrepeats      = kwa.get("nrepeats",      6)
        self.kernel_window = kwa.get("kernel_window", 4)
        self.kernel_width  = kwa.get("kernel_width",  3)

    def __call__(self, data):
        osamp   = (self.oversampling//2) * 2 + 1
        maxcorr = self.maxcorr*osamp

        kern  = np.arange(2*self.kernel_window*osamp+1, dtype = 'f4') / osamp
        kern  = np.exp(-.5*((kern-self.kernel_window)/self.kernel_width)**2)
        kern /= kern.sum()

        ref   = np.empty((max(len(i) for i in data)*osamp+maxcorr*2,), dtype = 'f4')
        hists = []

        cur   = ref[:-2*maxcorr]
        for rng in data:
            cur.fill(0.)
            cur[osamp//2:len(rng)*osamp:osamp] = rng
            hists.append(fftconvolve(cur, kern, 'same'))

        bias = np.full((len(hists),), maxcorr+osamp//2, dtype = np.int32)
        for _ in range(self.nrepeats):
            ref.fill(0.)
            for start, hist in zip(bias, data):
                ref[start:start+len(hist)] += hist

            bias  = np.fromiter((np.argmax(np.correlate(ref, hist)) for hist in hists),
                                dtype = np.float32, count = len(hists))
            bias += maxcorr+osamp//2-(bias.max()+bias.min())//2

        ref = bias/osamp
        return np.subtract(ref, np.median(ref), out = ref)

    @classmethod
    def run(cls, data, **kwa):
        u"runs the algorithm"
        return cls(**kwa)(data)
