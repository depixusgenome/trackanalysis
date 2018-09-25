#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Basic stuff for dealing with peak calling
"""
from   typing       import (NamedTuple, Dict, Any, Optional, Union,
                            Iterator, Tuple, List, cast)
from   enum         import Enum
from   itertools    import product
import numpy        as     np
from   utils        import initdefaults

from ._core         import match as _match # pylint: disable=import-error

DEFAULT_BEST = float(np.finfo('f4').max)

class CobylaParameters(NamedTuple): # pylint: disable=missing-docstring
    rhobeg: Optional[Tuple[float,...]]
    rhoend: Optional[Tuple[float,...]]
    maxfun: Optional[float]
    catol:  Optional[float]

class LBFGSParameters(NamedTuple): # pylint: disable=missing-docstring
    threshold_param_rel: float
    threshold_param_abs: float
    threshold_func_rel:  float
    stopval:             float
    maxeval:             int

OptimType = Union[CobylaParameters, LBFGSParameters]

class Range(NamedTuple): # pylint: disable=missing-docstring
    center:  Optional[float]
    size:    float
    step:    float

class Distance(NamedTuple): # pylint: disable=missing-docstring
    value:   float
    stretch: float
    bias:    float

class Pivot(Enum):
    "The position of the pivot in the fit"
    absolute = 'absolute'
    top      = 'top'
    bottom   = 'bottom'


class Symmetry(Enum):
    "Which side to consider"
    both  = 'both'
    left  = 'left'
    right = 'right'

def config(self:OptimType, **kwa) -> Dict[str, float]:
    "returns the configuration"
    if isinstance(self, LBFGSParameters):
        vals = ('threshold_param_rel',
                'threshold_param_abs',
                'threshold_func_rel',
                'stopval', 'maxeval') # type: Tuple[str, ...]
    else:
        vals = 'rhobeg', 'rhoend', 'catol', 'maxfun'
    kwa.update({i: getattr(self, i) for i in vals if getattr(self, i) is not None})
    return kwa

class OptimizationParams:
    "Optimizing parameters"
    stretch          = Range(1./8.8e-4, 200., 100.)
    bias             = Range(None,       60.*8.8e-4, 60.*8.8e-4)
    optim: OptimType = LBFGSParameters(1e-4, 1e-8, 1e-4, 1e-8, 100)
    @initdefaults(frozenset(locals()))
    def __init__(self, **kwa):
        pass
    def constraints(self):
        "the stretch & bias constraints for the chisquare"
        scstr = ((self.stretch.center if self.stretch.center else 0.) - self.stretch.size,
                 (self.stretch.center if self.stretch.center else 0.) + self.stretch.size)
        bcstr = None
        if self.bias.center is not None:
            pots: List[float] = [(self.bias.center - self.bias.size)*scstr[0],
                                 (self.bias.center - self.bias.size)*scstr[1],
                                 (self.bias.center + self.bias.size)*scstr[0],
                                 (self.bias.center + self.bias.size)*scstr[1]]
            bcstr = min(pots), max(pots)
        return scstr, bcstr

class GriddedOptimization(OptimizationParams):
    "Optimizes using a rectangular grid"
    symmetry = Symmetry.left
    @initdefaults(frozenset(locals()))
    def __init__(self, **kwa):
        super().__init__(**kwa)

    @property
    def grid(self) -> Union[np.ndarray, Iterator[Tuple[float, ...]]]:
        "returns the range on which the attribute is explored"
        return product(self.__gridded(self.stretch), self.__gridded(self.bias))

    def optimconfig(self, **kwa) -> Dict[str, Any]:
        "returns the configuration"
        return config(self.optim, **kwa)

    @staticmethod
    def __gridded(val):
        cnt = max(1, (int(2.*val.size/val.step+0.5)//2)*2+1)
        if cnt == 1:
            return np.array([0. if val.center is None else val.center], dtype = 'f4')
        if val.center is None:
            return np.linspace(-val.size, val.size, cnt)
        return np.linspace(val.center-val.size, val.center+val.size, cnt)

class PointwiseOptimization(OptimizationParams):
    "Optimizes using a grid where nodes are such that at least one match occurs"
    bases           = (20, 20)
    dataprecisions  = 1., 1e-3
    @initdefaults(frozenset(locals()))
    def __init__(self, **kwa):
        super().__init__(**kwa)

    def pointgrid(self, ref:np.ndarray, exp:np.ndarray) -> Iterator[Tuple[float, float]]:
        "computes stretch and bias for potential pairings"
        minstretch = cast(float, self.stretch.center) - cast(float, self.stretch.size)
        maxstretch = cast(float, self.stretch.center) + cast(float, self.stretch.size)
        if self.bias.center is None:
            minbias, maxbias = -1e5, 1e5
        else:
            minbias = self.bias.center - self.bias.size
            maxbias = self.bias.center + self.bias.size

        basemax = ref[-1] + self.bases[1]
        zeromin = ref[0]  - self.bases[0]
        zeromax = ref[0]  + self.bases[0]
        def _compute(iref, jref, iexp, jexp):
            rho  = (ref[iref]-ref[jref])/(exp[iexp] - exp[jexp])
            return rho, exp[iexp]-ref[iref]/rho

        pot = iter(_compute(iref, jref, iexp, jexp)
                   for iref in range(len(ref)-1)
                   for jref in range(iref+1, len(ref))
                   for iexp in range(len(exp)-1)
                   for jexp in range(iexp+1, len(exp)))
        valid = set((int(val[0]/self.dataprecisions[0]+0.5),
                     int(val[1]/self.dataprecisions[1]+0.5)) for val in pot
                    if (minstretch  <= val[0] <= maxstretch
                        and minbias <= val[1] <= maxbias
                        and val[0]*(exp[-1]-val[1]) <= basemax
                        and zeromin <= val[0]*(exp[0] -val[1]) <= zeromax
                       ))
        return iter((val[0]*self.dataprecisions[0], val[1]*self.dataprecisions[1])
                    for val in valid)

    def optimconfig(self, **kwa) -> Dict[str, Any]:
        "returns the configuration"
        return config(self.optim, **kwa)

def _chi2cost(ref, exp, pairs, symmetry, dist):
    if symmetry is Symmetry.both:
        dist += (len(exp)+len(ref)-2.*len(pairs))**2
        return np.sqrt(dist/(len(exp)+len(ref))) if len(exp)+len(ref) else np.finfo('f4').max

    if symmetry is Symmetry.left:
        dist += (len(ref)-len(pairs))**2
        return np.sqrt(dist/len(ref)) if len(ref) else np.finfo('f4').max

    dist += (len(exp)-len(pairs))**2
    return np.sqrt(dist/len(exp)) if len(exp) else np.finfo('f4').max

def chisquare(ref       : np.ndarray, # pylint: disable=too-many-arguments
              exp       : np.ndarray,
              firstpeak : bool,
              symmetry  : Symmetry,
              window    : float,
              stretch   : float,
              bias      : float,
              stretchcstr: tuple = None,
              biascstr:    tuple = None):
    """
    We use the GaussianProductFit results to match exp then estimate
    the best Χ² fit between matched exp, adding their count as well.
    """
    def _pairs(params):
        tmp   = exp*params[0]+params[1]
        pairs = _match.compute(ref, tmp, window)
        if firstpeak and len(pairs) and any(i == 0 for i in pairs[0]):
            return pairs[1:]
        return pairs

    def _fit(pairs):
        xvals, yvals = exp[pairs[:,1]], ref[pairs[:,0]]
        cov          = np.cov(yvals, xvals)
        newstretch   = cov[0,1]/cov[1,1]
        if stretchcstr is not None:
            newstretch = max(stretchcstr[0], min(stretchcstr[1], newstretch))

        newbias = np.mean(yvals)-newstretch*np.mean(xvals)
        if biascstr is not None:
            newbias = max(biascstr[0], min(biascstr[1],  newbias))

        params = newstretch, newbias
        return params, _pairs(params)

    pairs = _pairs((stretch, bias))
    if len(pairs) > 1:
        params, newpairs  = _fit(pairs)
        if len(newpairs) > len(pairs):
            params, newpairs = _fit(newpairs)
        if params is not None:
            pairs  = newpairs
        else:
            params = stretch, bias

        dist  = ((params[0]*exp[pairs[:,1]]+params[1] - ref[pairs[:,0]])**2).sum()
        dist /= window**2
    else:
        params = (stretch, bias)
        dist   = 0.

    return _chi2cost(ref, exp, pairs, symmetry, dist), params[0], params[1]

def chisquarevalue(ref       : np.ndarray, # pylint: disable=too-many-arguments
                   exp       : np.ndarray,
                   firstpeak : bool,
                   symmetry  : Symmetry,
                   window    : float,
                   stretch   : float,
                   bias      : float):
    """
    We use the GaussianProductFit results to match exp then estimate
    the best Χ² fit between matched exp, adding their count as well.
    """
    tmp   = exp*stretch+bias
    pairs = _match.compute(ref, tmp, window)
    if firstpeak and len(pairs) and any(i == 0 for i in pairs[0]):
        pairs = pairs[1:]

    if len(pairs) > 1:
        dist  = ((stretch*exp[pairs[:,1]]+bias - ref[pairs[:,0]])**2).sum()
        dist /= window**2
    else:
        dist = 0.

    return _chi2cost(ref, exp, pairs, symmetry, dist), stretch, bias
