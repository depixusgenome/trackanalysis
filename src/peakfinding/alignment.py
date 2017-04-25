#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Cycle alignment: define an absolute zero common to all cycles"
from   typing                   import (Union, Optional, # pylint: disable=unused-import
                                        Sequence, Iterable, Iterator, cast)

import numpy  as     np
from   numpy.lib.stride_tricks  import as_strided

from   utils                    import (kwargsdefaults, initdefaults, updatecopy,
                                        asobjarray, EVENTS_DTYPE)
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
    * *factors*:   the factor to apply to the precision at each iteration.
    * *projector*: how to project cycles unto an axis
    """
    factors    = [2, 2, 1, 1]
    zcost      = 0.05         # type: Optional[float]
    maxmove    = 5
    projector  = Histogram()
    subpixel   = None         # type: Optional[SubPixelPeakPosition]
    @initdefaults(locals().keys(), projector = 'update')
    def __init__(self, **_):
        pass

    def __build_cost(self, maxt):
        if not self.zcost:
            return 1

        vals = np.arange(1, maxt//2)
        cost = self.zcost/self.projector.exactoversampling
        vals = 1. - cost*np.concatenate([vals[::-1], [0, 0], vals])
        return vals

    def __argmax(self, cur, ref, cost):
        arr = cost*np.dot(cur, ref)
        ind = np.argmax(arr)
        if self.subpixel is None:
            return ind

        subp = self.subpixel(arr, ind)              # pylint: disable=not-callable
        return ind if subp is None else subp

    @kwargsdefaults
    def __call__(self,
                 data:      Union[np.ndarray, Iterable[np.ndarray]],
                 precision: Optional[float] = None) -> np.ndarray:
        data  = asobjarray(data)
        first = next((i for i in data if len(i)), None)
        if first is None:
            return

        osamp = self.projector.exactoversampling
        maxt  = 2*self.maxmove*osamp

        project = updatecopy(self.projector,
                             edge      = (self.maxmove+self.projector.kernel.width)*2)
        if precision:
            project.precision = precision

        if getattr(first, 'dtype', 'f') == EVENTS_DTYPE or not np.isscalar(first[0]):
            data = project.eventpositions(data)
        project.zmeasure = None

        cost  = self.__build_cost(maxt)
        bias  = None
        for fact in self.factors:
            hists, _, width = project(data,
                                      bias      = bias,
                                      separate  = True,
                                      precision = project.precision*fact)
            hists = tuple(as_strided(cur,
                                     shape   = (maxt, len(cur)-maxt),
                                     strides = (cur.strides[0],)*2)
                          for cur in hists)

            ref   = np.sum  ([cur[maxt//2] for cur in hists], 0)

            cur   = np.array([self.__argmax(cur, ref, cost) for cur in hists])*(-width)
            bias  = cur if bias is None else np.add(bias, cur, out = bias)
            bias -= np.median(bias)
        return bias

    @classmethod
    def run(cls, data: Iterable[np.ndarray], **kwa):
        u"runs the algorithm"
        return cls(**kwa)(data)
