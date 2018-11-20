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

    def __cost(self, pairs, dist):
        exp, ref = self.exp, self.ref
        if self.singlestrand:
            maxv  = (ref[-1]-self.bias)/self.stretch
            tmp   = exp[np.searchsorted(exp, maxv):]
            if len(tmp):
                tmp   = self.stretch*tmp # don't forget to use a copy of the vector!
                tmp  += self.bias
                tmp  -= ref[-1]
                tmp **= 2
                dist += tmp.sum()/self.window**2

        if self.symmetry is Symmetry.both:
            dist += (len(exp)+len(ref)-2.*len(pairs))**2
            return np.sqrt(dist/(len(exp)+len(ref))) if len(exp)+len(ref) else DEFAULT_BEST

        if self.symmetry is Symmetry.left:
            dist += (len(ref)-len(pairs))**2
            return np.sqrt(dist/len(ref)) if len(ref) else DEFAULT_BEST

        dist += (len(exp)-len(pairs))**2
        return np.sqrt(dist/len(exp)) if len(exp) else DEFAULT_BEST

    def __value(self, pairs, stretch, bias) -> Tuple[float, float, float]:
        if len(pairs) > 1:
            tmp   = self.exp[pairs[:,1]]
            tmp  *= stretch
            tmp  += bias
            tmp  -= self.ref[pairs[:,0]]
            tmp **= 2
            dist  = tmp.sum()/self.window**2
        else:
            dist = 0.

        return self.__cost(pairs, dist), stretch, bias
