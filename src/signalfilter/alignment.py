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

def extremum(data, mode: 'Union[str,AlignmentMode]', window:int = 5) -> np.ndarray:
    u"Returns an array of biases computed as the minimum or maximum of rolling medians"
    itr = (j[len(j) % window:].reshape((len(j)/window, window)).median(axis = 0)
           for j in data) if window > 2 else data
    fcn = getattr(np, AlignmentMode(mode).value)
    res = numpy.fromiter((-fcn(i) for i in itr), dtype = numpy.float32)
    return np.subtract(res, res.median(), out = res)

def correlation(data, refrange, refgau, nrepeats):
    u"""
    Repeatedly fits a cycle's histogram to all others in order to find the
    best alignment
    """
    size  = max(len(i) for i in data)
    delta = 2*refrange+1
    bias  = numpy.full((size,), refrange+2*delta, dtype = numpy.int32)

    kern  = np.exp(-(np.arange(2*refgau+1, dtype = np.float32) - refgau)**2 *.5)
    ref   = np.empty(((size+4)*delta),     dtype = np.float32)
    cur   = ref[delta:-delta]

    hists = []
    for rng in data:
        cur[:]                          = 0.
        cur[refrange+1:-refrange:delta] = rng
        hists.append(fftconvolve(cur, kern, 'same'))

    for _ in range(nrepeats):
        ref[:] = 0.
        for i, rng in enumerate(data):
            cur  = ref[bias[i]::delta][:len(rng)]
            cur += rng[:len(cur)]
        hist1    = fftconvolve(ref, kern, 'same')

        bias[:]  = (np.argmax(np.correlate(hist1, hist2)) for hist2 in hists)
        bias    += refrange+2*delta-(bias.max()-bias.min())//2

    ret  = bias/float(delta)
    ret -= ret.median()
    return ret
