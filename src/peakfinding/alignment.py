#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Cycle alignment: define an absolute zero common to all cycles"
from   typing                   import (Union, Optional, # pylint: disable=unused-import
                                        Sequence, Iterable, Iterator, cast)
from   copy                     import copy

import numpy  as     np
from   numpy.lib.stride_tricks  import as_strided

from   utils                    import kwargsdefaults, initdefaults
from   .histogram               import (Histogram,       # pylint: disable=unused-import
                                        SubPixelPeakPosition)

class PeakCorrelationAlignment:
    u"""
    Finds biases which correlate best a cycle's histogram to the histogram of
    all cycles. This repeated multiple times with the latter histogram taking
    prior biases into account.

    Biases are furthermore centered at zero around their median

    Attributes:

    * *maxmove*:   max amount by which a cycle may be translated.
    * *nrepeats*:  the number of times the procedure is repeated
    * *projector*: how to project cycles unto an axis
    """
    nrepeats   = 6
    maxmove    = 5
    projector  = Histogram(zmeasure = None)
    subpixel   = None                               # type: Optional[SubPixelPeakPosition]
    @initdefaults(locals().keys(), projector = 'update')
    def __init__(self, **_):
        pass

    def __argmax(self, cur, ref):
        arr = np.dot(cur, ref)
        ind = np.argmax(arr)
        if self.subpixel is None:
            return ind

        subp = self.subpixel(arr, ind)              # pylint: disable=not-callable
        return ind if subp is None else subp

    @kwargsdefaults
    def __call__(self, data: Union[np.ndarray, Iterable[np.ndarray]]) -> np.ndarray:
        bias  = None
        osamp = self.projector.exactoversampling
        maxt  = 2*self.maxmove*osamp

        project          = copy(self.projector)
        project.edge     = (self.maxmove+project.kernel.width)*2
        project.zmeasure = None

        for _ in range(self.nrepeats):
            hists = project(data, bias = bias, separate = True)[0]
            hists = tuple(as_strided(cur,
                                     shape   = (maxt, len(cur)-maxt),
                                     strides = (cur.strides[0],)*2)
                          for cur in hists)

            ref   = np.sum  ([cur[maxt//2] for cur in hists], 0)

            cur   = np.array([self.__argmax(cur, ref) for cur in hists])
            cur   = (np.median(cur)-cur) / osamp

            bias  = cur if bias is None else np.add(bias, cur, out = bias)
        return bias

    @classmethod
    def run(cls, data: Iterable[np.ndarray], **kwa):
        u"runs the algorithm"
        return cls(**kwa)(data)
