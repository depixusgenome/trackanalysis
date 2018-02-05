#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Cycle alignment: define an absolute zero common to all cycles"
from   typing                  import (Union, Optional, # pylint: disable=unused-import
                                        Sequence, Iterable, Iterator,
                                        cast)

import numpy  as     np
from   numpy.lib.stride_tricks import as_strided

from   utils                   import (initdefaults, updatecopy, kwargsdefaults,
                                        asobjarray, EVENTS_DTYPE)
from   .histogram              import Histogram
from   .groupby                import  SubPixelPeakPosition

class PeakCorrelationAlignment:
    """
    Finds biases which correlate best a cycle's histogram to the histogram of
    all cycles. This repeated multiple times with the latter histogram taking
    prior biases into account.

    Biases are furthermore centered at zero around their median.

    # Attributes

    * *actions*:   a list of aligment actions with their options
    * *subpixel*:  algorithm for subpixel precision on the correlation peaks
    * *projector*: how to project cycles unto an axis
    """
    class WorkTable:
        "Contains data to be saved from action to action"
        def __init__(self, parent, precision, data, **_):
            self.parent    = parent
            self.precision = precision
            self.data      = data
            self.cost      = (1,)

    class Action:
        """
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

        def costarray(self, wtab, projector) -> Union[int,np.ndarray]:
            "computes a z-cost array"
            if not self.zcost:
                return lambda x: x,

            osamp = projector.exactoversampling
            if wtab.cost[1:] == (self.maxmove, self.zcost, osamp):
                return wtab.cost

            arr   = np.arange(1,  self.maxmove*osamp)
            cost  = self.zcost/osamp
            arr   = 1. - cost*np.concatenate([arr[::-1], [0, 0], arr])

            return lambda x: x*arr, self.maxmove, self.zcost, osamp

        def projector(self, wtab):
            "projects the data"
            edge = (self.maxmove + wtab.parent.projector.kernel.width)*2
            return updatecopy(wtab.parent.projector,
                              zmeasure  = None,
                              edge      = edge,
                              precision = wtab.precision*self.factor)

        def reference(self, _, projector, hists):
            "computes a reference"
            maxt = projector.exactoversampling*self.maxmove*2
            return np.mean([i[maxt//2] for i in hists[0]], 0)

        @staticmethod
        def center(bias):
            "centers the bias"
            bias -= np.median(bias)
            return bias

        def good(self, wtab):
            "finds cycles to align"
            good = np.array([len(i) for i in wtab.data]) >= self.minevents
            if not np.any(good):
                return None
            return good

        def argmax(self, wtab):
            "computes the argmax function"
            cost     = wtab.cost[0]
            subpixel = wtab.parent.subpixel
            if self.subpixel and callable(subpixel):
                def _argmax(ref, cur):
                    arr  = cost(np.dot(cur, ref))
                    ind  = np.argmax(arr)
                    subp = subpixel(arr, ind)
                    return ind if subp is None else subp
                return _argmax

            return lambda ref, cur: np.argmax(cost(np.dot(cur, ref)))

        def hists(self, wtab, projector, bias, good):
            "creates the histograms"
            bias  = bias if bias is None else bias[good]
            hists = projector(wtab.data[good], bias = bias, separate = True)

            maxt   = projector.exactoversampling*self.maxmove*2
            matrix = tuple(as_strided(cur,
                                      shape   = (maxt, len(cur)-maxt),
                                      strides = (cur.strides[0],)*2)
                           for cur in hists[0])
            return (matrix,)+hists[1:]

        def bias(self, wtab, projector, bias):
            "finds the bias"
            good = self.good(wtab)
            if good is None:
                return bias

            hists = self.hists(wtab, projector, bias, good)
            ref   = self.reference(wtab, projector, hists)

            argmax = self.argmax(wtab)
            found  = np.array([argmax(ref, i) for i in hists[0]])

            if bias is None:
                bias = np.zeros((len(wtab.data),), dtype = 'f4')

            maxt        = projector.exactoversampling*self.maxmove*2
            bias[good] -= (found - maxt//2)*hists[2]
            return self.center(bias)

        def __call__(self, wtab, bias):
            projector = self.projector(wtab)
            wtab.cost = self.costarray(wtab, projector)
            return self.bias(wtab, projector, bias)

    actions   = [Action(),
                 Action(),
                 Action(factor = 1),
                 Action(factor = 1, minevents = 1, maxmove = 2, subpixel = True)]
    projector = Histogram()
    subpixel  = SubPixelPeakPosition()

    __KEYS    = frozenset(locals())
    @initdefaults(__KEYS,
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

    @kwargsdefaults(__KEYS)
    def __call__(self,
                 data:      Union[np.ndarray, Iterable[np.ndarray]],
                 precision: float = None, **kwa) -> np.ndarray:
        data  = asobjarray(data)
        first = next((i for i in data if len(i)), None)
        if first is None:
            return None

        if getattr(first, 'dtype', 'f') == EVENTS_DTYPE or not np.isscalar(first[0]):
            precision = self.projector.getprecision(precision, data)
            data      = self.projector.eventpositions(data)
        elif precision is None:
            precision = self.projector.precision

        wtab = self.WorkTable(self, precision, data, **kwa) # type: ignore
        bias = None
        for action in self.actions:
            bias = action(wtab, bias)
        return bias

    @classmethod
    def run(cls, data: Iterable[np.ndarray], **kwa):
        "runs the algorithm"
        return cls(**kwa)(data)
