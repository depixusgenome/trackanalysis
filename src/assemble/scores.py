#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u'''
defines a list of scoring functors for sequence assembly
'''
from typing import Tuple, List # pylint: disable=unused-import
import scipy
import numpy
from utils import initdefaults
from . import data # pylint: disable=unused-import
from ._types import SciDist # pylint: disable=unused-import

class DefaultCallable:
    u'defines a Default Callable'
    def __init__(self,res):
        self.res=res
    def __call__(self,*args,**kwargs):
        u'returns res'
        return self.res

class SOMConstraint:
    u'functor for scipy.optimize.minimize constraints'
    index=-1
    _epsi = 0.0001 # type: float
    @initdefaults
    def __init__(self,**kwa):
        pass
    def __call__(self,xstate):
        return xstate[self.index+1]-xstate[self.index]-self._epsi

class OptiDistPerm:
    u'''
    minimize translational cost of permutation
    '''
    perm = (-1,) # type: Tuple[int]
    dists = [] # type: List[SciDist]
    __epsi=-1 # type:float
    @initdefaults()
    def __init__(self,**kwa):
        pass

    @property
    def epsi(self)->float:
        u'returns float precision'
        if self.__epsi==-1:
            self.__setattr__("__epsi",0.001*min([self.dists[i].std() for i in self.perm]))
        return self.__epsi

    def run(self,xinit=None)->numpy.ndarray:
        u'returns the PERMUTATED state which maximise the probability'
        constraints = []
        for idx in range(len(self.perm[:-1])):
            constraints.append({"type":"ineq",
                                "fun":SOMConstraint(index=idx,
                                                    _epsi=self.epsi)})

        if xinit is None:
            xinit = [self.dists[i].mean() for i in self.perm]

        fun = CostPermute(perm=self.perm,dists=self.dists)
        return scipy.optimize.minimize(fun,xinit,constraints=constraints).x


class OptiKPerm: # need to complete pytest
    u'''
    returns the position of the permuted oligos
    '''
    kperm=[] # type: List[data.OligoPeaks]
    __pstate=[] # type: List[float]
    @initdefaults
    def __init__(self,**kwa):
        pass

    @property
    def __perm(self):
        u'returns perm for OptiDistPerm'
        return list(range(len(self.kperm)))

    @property
    def pstate(self):
        u'calls OptiDistPerm, returns permuted xstate'
        if self.__pstate==[]:
            dists = [oli.dist for oli in self.kperm]
            self.__pstate = OptiDistPerm(perm=self.__perm,dists=dists).run()
        return self.__pstate

    def cost(self):
        u'the lower the cost the better'
        return PDFCost(oligos=self.kperm)(self.pstate)

class CostPermute:
    u'returns the "cost" of translations due to permutation of oligo peaks'
    perm = (-1,) # type: Tuple[int]
    dists = [] # type: List[SciDist]
    oligos = [] # type: List[data.OligoPeak]
    @initdefaults()
    def __init__(self,**kwa):
        pass

    @property
    def get_dists(self):
        u'defines dist from oligos'
        if self.dists==[]:
            self.dists=[i.dist for i in self.oligos]
        return self.dists

    def __call__(self,xstate)->float:
        return -numpy.product([self.get_dists[vlp].pdf(xstate[idp])
                               for idp,vlp in enumerate(self.perm)])


class PDFCost:
    u'returns the "cost" in probability density of position'
    dists = [] # type: List[SciDist]
    oligos = [] # type: List[data.OligoPeak]
    @initdefaults()
    def __init__(self,**kwa):
        pass

    @property
    def get_dists(self):
        u'defines dist from oligos'
        if self.dists==[]:
            self.dists=[i.dist for i in self.oligos]
        return self.dists

    def __call__(self,xstate)->float:
        return -numpy.product([self.get_dists[idp].pdf(val)
                               for idp,val in enumerate(xstate)])

class ScoreAssembly: # should be ok # but must be tested
    u'''
    given an assembly (list of oligos in the correct order)
    returns (number of overlaps,cost of permutation)
    '''
    assembly=[] # type: List[data.OligoPeak]
    ooverl=-1 # type: int
    @initdefaults
    def __init__(self,**kwa):
        pass

    def run(self):
        u'compute score'
        return tuple([self.__density,self.__overlaps])

    def __density(self)->float:
        return OptiKPerm(kperm=self.assembly).cost()

    def __overlaps(self)->int:
        u'''
        returns the number of consecutive overlaps between oligos
        '''
        return len([idx for idx,val in enumerate(self.assembly[1:])
                    if len(data.Oligo.tail_overlap(self.assembly[idx].seq,
                                                   val.seq))==self.ooverl])
