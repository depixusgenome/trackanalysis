#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u'''
defines a list of scoring functors for sequence assembly
'''
from typing import Tuple, List, NamedTuple # pylint: disable=unused-import
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
    kperm=[] # type: List[data.OligoPeak]
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


ScoredKPerm = NamedTuple("ScoredKPerm",[("kperm",data.OligoPeakKPerm),
                                        ("density_cost",float),
                                        ("noverlaps",int)])

# still incorrect since __density (PDFCOST) should only take into account peaks
# whose position has changed
# and __overlaps should only consider local oligos (i.e. kpermids)
class ScoreAssembly:
    u'''
    given an assembly (list of oligos in the correct order)
    returns (number of overlaps,cost of permutation)
    '''
    okperm=data.OligoPeakKPerm() # type: data.OligoPeakKPerm
    ooverl=-1 # type: int
    @initdefaults
    def __init__(self,**kwa):
        pass

    def run(self)->ScoredKPerm:
        u'compute score'
        return ScoredKPerm(kperm=self.okperm,
                           density_cost=self.__density(),
                           noverlaps=self.__overlaps())

    def __density(self)->float: # to check
        changed=[self.okperm.kperm[idx]
                 for idx,val in enumerate(self.okperm.kpermids)
                 if val in self.okperm.changes]
        return OptiKPerm(kperm=changed).cost()

    def __overlaps(self)->int: # to check
        u'''
        returns the number of consecutive overlaps between oligos in kpermids
        '''
        kperm=self.okperm.kperm
        return len([idx for idx,val in enumerate(kperm[1:])
                    if len(data.Oligo.tail_overlap(kperm[idx].seq,
                                                   val.seq))==self.ooverl])

    def __call__(self,okperm:data.OligoPeakKPerm)->ScoredKPerm:
        self.okperm=okperm
        return self.run()


class ScoreFilter:
    u'''
    filter out ScoredKPerm which cannot lead to the 'best' score
    '''
    scorekperms=[] # type: List[ScoredKPerm]
    @initdefaults(frozenset(locals()))
    def __init__(self,**kwa):
        pass

    def run(self)->List[ScoredKPerm]:
        u'''
        implements minimal condition for optimal score
        for the same value of overlaps, filters out 
        the scores with density_cost > lower(density_cost)*(1-0.1)
        '''
        # to implement
        return self.scorekperms
