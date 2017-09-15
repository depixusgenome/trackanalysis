#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Basic stuff for dealing with peak calling
"""
from   typing       import NamedTuple, Dict, Any, Optional, Union, Iterator, Tuple
from   itertools    import product
import numpy        as     np
from   utils        import initdefaults

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

OPTIM_TYPE = Union[CobylaParameters, LBFGSParameters]

class Range(NamedTuple): # pylint: disable=missing-docstring
    center:  Optional[float]
    size:    float
    step:    float

class Distance(NamedTuple): # pylint: disable=missing-docstring
    value:   float
    stretch: float
    bias:    float

def config(self:OPTIM_TYPE, **kwa) -> Dict[str, float]:
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

class GriddedOptimization:
    "Optimizes using a rectangular grid"
    symmetry          = False
    stretch           = Range(1./8.8e-4, 200., 100.)
    bias              = Range(None,       60.*8.8e-4, 60.*8.8e-4)
    optim: OPTIM_TYPE = LBFGSParameters(1e-4, 1e-8, 1e-4, 1e-8, 100)

    @initdefaults(frozenset(locals()))
    def __init__(self, **kwa):
        pass

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

class PointwiseOptimization:
    "Optimizes using a grid where nodes are such that at least one match occurs"
    bases           = (20, 20)
    stretch         = Range(1./8.8e-4, 200., 50.)
    bias            = Range(None,       20.*8.8e-4, 20.*8.8e-4)
    dataprecisions  = 1., 1e-3
    optim           = LBFGSParameters(1e-4, 1e-8, 1e-4, 1e-8, 100)
    @initdefaults(frozenset(locals()))
    def __init__(self, **kwa):
        pass

    def pointgrid(self, ref:np.ndarray, exp:np.ndarray) -> Iterator[Tuple[float, float]]:
        "computes stretch and bias for potential pairings"
        minstretch = self.stretch.center - self.stretch.size
        maxstretch = self.stretch.center + self.stretch.size
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
