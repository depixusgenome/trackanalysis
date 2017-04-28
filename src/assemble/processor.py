#!/usr/bin/env python3
# -*- coding: utf-8 -*-

u'''
regroups functions and classes to complement assembler
'''

import itertools
from typing import List # pylint: disable=unused-import
import numpy
from utils.logconfig import getLogger
from utils import initdefaults

from . import data
from ._types import SciDist

LOGS = getLogger(__name__)


class OptiDistPerm: # pytest
    u'''
    optimize translational cost of permutation
    '''
    perm:Tuple[int] = ()
    dists:List[SciDist] = []
    @initdefaults()
    def __init__(self,**kwa):
        # assert len(perm)==len(dists) # ??
        self._epsi:float = 0.001*min([dists[i].std() for i  in perm])

    def run(self)->numpy.ndarray:
        u'returns the PERMUTATED state which maximise the probability'
        constraints = []
        for idx in range(len(self.perm[:-1])):
            constraints.append({"type":"ineq",
                                "fun":SOMConstraint(idx,self._epsi)})

        xinit = [self.dists[i].mean() for i in self.perm]
        fun = CostPermute(self.dists,self.perm)
        return scipy.optimize.minimize(fun,xinit,constraints=constraints).x

class CostPermute:
    u'returns the "cost" of translations due to permutation of oligo peaks'
    perm:Tuple(int) = ()
    dists:List[SciDist] = []
    @initdefaults
    def __init__(self,**kwa):
        pass
    def __call__(self,xstate):
        return -numpy.product([self.dists[vlp].pdf(xstate[idp])
                               for idp,vlp in enumerate(self.perm)])

class SOMConstraint:
    u'functor for scipy.optimize.minimize constraints'
    index:int = -1
    _epsi:float = -1.0
    @initdefaults
    def __init__(self,**kwa):
        pass
    def __call__(self,xstate):
        return xstate[self.index+1]-xstate[self.index]-self._epsi



class ComputeStates:
    u'Computes possible permutation between'
    collection:BCollection=BCollection()
    def __init__(self,**kwa):
        pass
    def run()->numpy.ndarray:
        u'returns the new xstates to explore'
        
