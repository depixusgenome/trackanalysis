#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Cycle alignment: define an absolute zero common to all cycles"
from   typing       import Callable, Union, Any # pylint: disable=unused-import
from   enum         import Enum
from   scipy.signal import fftconvolve
import numpy; np = numpy # type: Any # pylint: disable=multiple-statements,invalid-name

class AlignmentMode(Enum):
    u"Computation modes for the derivate method."
    min = 'min'
    max = 'max'

def extremum(data, mode: 'Union[str,AlignmentMode]', binsize:int = 5) -> np.ndarray:
    u"""
    Returns an array of biases computed as the extremum of provided ranges.
    Biases are furthermore centered at zero around their median

    Parameters:

    * *mode*: the extremum to use
    * *binsize*: if > 2, the extremum is computed over the median of values binned
        by *binsize*.
    """
    itr = (np.median(j[len(j) % binsize:].reshape((len(j)//binsize, binsize)), axis = 0)
           for j in data) if binsize > 2 else data
    fcn = getattr(np, AlignmentMode(mode).value)
    res = numpy.fromiter((-fcn(i) for i in itr), dtype = numpy.float32)
    return np.subtract(res, np.median(res), out = res)

def correlation(data,                       # pylint: disable=too-many-arguments
                oversampling    : int = 5,
                maxcorr         : int = 4,
                nrepeats        : int = 6,
                kernel_window   : int = 4,
                kernel_width    : int = 3,
               ):
    u"""
    Finds biases which correlate best a cycle's histogram to the histogram of
    all cycles. This repeated multiple times with the latter histogram taking
    prior biases into account.

    Biases are furthermore centered at zero around their median

    Parameters:

    * *oversampling*: the amount by which histograms are oversampled. This is
        the computation's precision
    * *maxcorr*: max amount by which a cycle may be translated.
    * *nrepeats*: the number of times the procedure is repeated
    * *kernel_window*: the size of the smearing kernel
    * *kernel_width*: the distribution size of the smearing kernel
    """
    oversampling = (oversampling//2) * 2 + 1

    kern  = np.arange(2*kernel_window*oversampling+1, dtype = np.float32)
    kern  = np.exp(-.5*((kern-kernel_window)/(oversampling*kernel_width))**2)
    kern /= kern.sum()

    ref   = np.empty(((max(len(i) for i in data)+maxcorr*2)*oversampling),
                     dtype = np.float32)
    hists = []

    cur   = ref[:-oversampling*2*maxcorr]
    for rng in data:
        cur.fill(0.)
        cur[oversampling//2:len(rng)*oversampling:oversampling] = rng
        hists.append(fftconvolve(cur, kern, 'same'))

    bias = numpy.full((len(hists),), maxcorr+oversampling//2, dtype = numpy.float32)
    for _ in range(nrepeats):
        ref.fill(0.)
        for start, hist in zip(bias, data):
            ref[start:start+len(hist)] += hist

        bias  = np.fromiter((np.argmax(np.correlate(ref, hist)) for hist in hists),
                            dtype = np.float32, count = len(hists))
        bias += maxcorr+oversampling//2-(bias.max()+bias.min())//2

    ref = bias/oversampling
    return np.subtract(ref, np.median(ref), out = ref)
