#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Cycle alignment: define an absolute zero common to all cycles"
from   typing                   import (Union, Optional, # pylint: disable=unused-import
                                        Sequence, Iterable, Iterator,
                                        cast)

import numpy  as     np
from   numpy.lib.stride_tricks  import as_strided

from   utils                    import (initdefaults, updatecopy,
                                        asobjarray, EVENTS_DTYPE)
from   .histogram               import Histogram, SubPixelPeakPosition

class PeakCorrelationAlignment:
    u"""
    Finds biases which correlate best a cycle's histogram to the histogram of
    all cycles. This repeated multiple times with the latter histogram taking
    prior biases into account.

    Biases are furthermore centered at zero around their median

    Attributes:

    * *actions*:   a list of aligment actions with their options
    * *subpixel*:  algorithm for subpixel precision on the correlation peaks
    * *projector*: how to project cycles unto an axis
    """
    class Action:
        u"""
        Container class for computing a bias with given options.

        Attributes:

        * *factor*: multiplicative factor on the overall precision.
        * *zcost*: amount per unit of translation by which the cost function
        must outperform for that translation to be selected.
        * *maxmove*: max amount by which a cycle may be translated.
        * *minevents*: min number of events in a cycle required for a bias to
        be computed.
        """
        factor    = 2.
        zcost     = 0.05 # type: Optional[float]
        minevents = 2    # type: Optional[float]
        maxmove   = 5
        subpixel  = False
        @initdefaults(frozenset(locals()))
        def __init__(self, **_):
            pass

        def costarray(self, projector, arr) -> Union[int,np.ndarray]:
            "computes a z-cost array"
            if not self.zcost:
                return lambda x: x,

            osamp = projector.exactoversampling
            if arr[1:] == (self.maxmove, self.zcost, osamp):
                return arr

            arr   = np.arange(1,  self.maxmove*osamp)
            cost  = self.zcost/osamp
            arr   = 1. - cost*np.concatenate([arr[::-1], [0, 0], arr])

            return lambda x: x*arr, self.maxmove, self.zcost, osamp

        def projector(self, projector, precision):
            "projects the data"
            edge = (self.maxmove + projector.kernel.width)*2
            return updatecopy(projector,
                              zmeasure  = None,
                              edge      = edge,
                              precision = precision*self.factor)

        def bias(self,                  # pylint: disable=too-many-arguments
                 projector, data, bias, cost, subpixel):
            "finds the bias"
            good = np.array([len(i) for i in data]) >= self.minevents
            if not np.any(good):
                return bias

            if self.subpixel and subpixel:
                def _argmax(cur):
                    arr  = cost[0](np.dot(cur, ref))
                    ind  = np.argmax(arr)
                    subp = subpixel(arr, ind)
                    return ind if subp is None else subp
                argmax = _argmax
            else:
                argmax = lambda cur: np.argmax(cost[0](np.dot(cur, ref)))

            hists, _, width = projector(data[good],
                                        bias     = bias if bias is None else bias[good],
                                        separate = True)

            maxt  = projector.exactoversampling*self.maxmove*2
            hists = tuple(as_strided(cur,
                                     shape   = (maxt, len(cur)-maxt),
                                     strides = (cur.strides[0],)*2)
                          for cur in hists)

            ref   = np.mean([i[maxt//2] for i in hists], 0)
            found = np.array([argmax(i) for i in hists])

            if bias is None:
                bias = np.zeros((len(data),), dtype = 'f4')
            bias[good] -= (found - maxt//2)*width
            bias       -= np.median(bias)
            return bias

    actions   = [Action(),
                 Action(),
                 Action(factor = 1),
                 Action(factor = 1, minevents = 1, maxmove = 2, subpixel = True)]
    projector = Histogram()
    subpixel  = SubPixelPeakPosition()

    @initdefaults(frozenset(locals()),
                  projector = 'update',
                  zcost     = lambda self, j: self.setzcost(j),
                  maxmove   = lambda self, j: self.setmaxmove(j),
                  factor    = lambda self, j: self.setfactor(j))
    def __init__(self, **_):
        pass

    def __set(self, attr, vals):
        "sets the attribute for all actions"
        if isinstance(vals, (list, tuple)):
            for action, val in zip(self.actions, vals):
                setattr(action, attr, val)
        else:
            for action in self.actions:
                setattr(action, attr, vals)

    def setzcost(self, cost):
        "sets the z-cost for all actions"
        self.__set('zcost', cost)

    def setmaxmove(self, mmove):
        "sets max move for all actions"
        self.__set('maxmove', mmove)

    def setfactor(self, factor):
        "sets max move for all actions"
        self.__set('factor', factor)

    def __call__(self,
                 data:      Union[np.ndarray, Iterable[np.ndarray]],
                 precision: Optional[float] = None) -> np.ndarray:
        data  = asobjarray(data)
        first = next((i for i in data if len(i)), None)
        if first is None:
            return

        if getattr(first, 'dtype', 'f') == EVENTS_DTYPE or not np.isscalar(first[0]):
            precision = self.projector.getprecision(precision, data)
            data      = self.projector.eventpositions(data)
        elif precision is None:
            precision = self.projector.precision

        cost  = 1,
        bias  = None
        for action in self.actions:
            projector = action.projector(self.projector, precision)
            cost      = action.costarray(projector, cost)
            bias      = action.bias     (projector, data, bias, cost, self.subpixel)
        return bias

    @classmethod
    def run(cls, data: Iterable[np.ndarray], **kwa):
        u"runs the algorithm"
        return cls(**kwa)(data)
