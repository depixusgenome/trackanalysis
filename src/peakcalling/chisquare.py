#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Basic stuff for computing a chisquare
"""
from   typing       import Optional,  Tuple
import numpy        as     np

from   ._core       import match as _match # pylint: disable=import-error
from   ._base       import Symmetry, DEFAULT_BEST

class ChiSquare: # pylint: disable=too-many-instance-attributes
    "compute Χ²"
    def __init__(self,  # pylint: disable=too-many-arguments
                 ref:          np.ndarray,
                 exp:          np.ndarray,
                 window:       float,
                 stretch:      float    = 1.,
                 bias:         float    = 0.,
                 symmetry:     Symmetry = Symmetry.both,
                 singlestrand: bool     = False,
                 convert:      bool     = False) -> None:
        self.ref          = ref
        self.exp          = exp
        self.window       = window
        self.stretch      = stretch
        self.bias         = -bias*stretch if convert else bias
        self.symmetry     = symmetry
        self.convert      = convert
        self.singlestrand = singlestrand

    @property
    def baseline(self) -> bool:
        "whether the reference has 0 in its peaks"
        return len(self.ref) > 0 and self.ref[0] == 0

    def update(self, stretch, bias, convert):
        "resets the stretch and bias"
        self.stretch = stretch
        self.bias    = -bias*stretch if convert else bias
        return self

    def value(self) -> Tuple[float, float, float]:
        """
        We use the GaussianProductFit results to match exp then estimate
        the best Χ² fit between matched exp, adding their count as well.
        """
        return self.__value(self.__pairs(self.stretch, self.bias), self.stretch, self.bias)

    def optimize(self,
                 stretchcstr: Optional[Tuple[float, float]] = None,
                 biascstr:    Optional[Tuple[float, float]] = None
                )-> Tuple[float, float, float]:
        """
        We use the GaussianProductFit results to match exp then estimate
        the best Χ² fit between matched exp, adding their count as well.
        """
        pairs = self.__pairs(self.stretch, self.bias)
        if len(pairs) > 1:
            params, newpairs  = self.__fit(pairs, stretchcstr, biascstr)
            if len(newpairs) > len(pairs):
                params, newpairs = self.__fit(newpairs, stretchcstr, biascstr)
            if params is not None:
                pairs  = newpairs
            else:
                params = self.stretch, self.bias
            return self.__value(pairs, *params)

        return self.__value(pairs, self.stretch, self.bias)

    def __pairs(self, stretch, bias):
        tmp   = self.exp*stretch+bias
        return _match.compute(self.ref, tmp, self.window)

    def __fit(self, pairs, stretch, bias):
        xvals, yvals = self.exp[pairs[:,1]], self.ref[pairs[:,0]]
        cov          = np.cov(yvals, xvals)
        newstretch   = cov[0,1]/cov[1,1]
        if stretch is not None:
            newstretch = max(stretch[0], min(stretch[1], newstretch))

        newbias = np.mean(yvals)-newstretch*np.mean(xvals)
        if bias is not None:
            newbias = max(bias[0], min(bias[1],  newbias))

        params = newstretch, newbias
        return params, self.__pairs(*params)

    def __delta(self, arr, val, stretch, bias):
        if len(arr) == 0:
            return 0
        arr   = stretch*arr # don't forget to use a copy of the vector!
        arr  += bias
        arr  -= val
        arr **= 2
        return arr.sum()/self.window**2


    def __value(self, pairs, stretch, bias) -> Tuple[float, float, float]:
        exp, ref = self.exp, self.ref
        if len(exp) == 0 or len(ref) == 0 or len(pairs) == 0:
            return DEFAULT_BEST, stretch, bias

        dist     = 0.
        if len(pairs) > 1:
            dist = self.__delta(exp[pairs[:,1]], ref[pairs[:,0]], stretch, bias)

        if self.singlestrand and len(ref):
            val   = (ref[-1]-bias)/stretch
            dist += self.__delta(exp[np.searchsorted(exp, val):], val, stretch, bias)

        if self.baseline:
            val   = (ref[0]-bias)/stretch
            dist += self.__delta(exp[:np.searchsorted(exp, val)], val, stretch, bias)

        ntheo = (len(exp)+len(ref) if self.symmetry is Symmetry.both else
                 len(ref)          if self.symmetry is Symmetry.left else
                 len(exp))
        nvals = (2 if self.symmetry is Symmetry.both else 1) * len(pairs)
        return np.sqrt((dist+(ntheo-nvals)**2)/nvals), stretch, bias
