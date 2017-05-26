#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u'''
defines a list of scoring functors for sequence assembly
'''
from typing import Tuple, List, NamedTuple # pylint: disable=unused-import
import itertools
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
    index=-1 # type: int
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
    perm = tuple() # type: Tuple[int, ...]
    dists = [] # type: List[SciDist]
    __epsi=-1 # type:float
    @initdefaults(frozenset(locals()))
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
            # this line is time expensive
            self.__pstate = OptiDistPerm(perm=self.__perm,dists=dists).run()
        return self.__pstate

    def cost(self):
        u'the lower the cost the better'
        return PDFCost(oligos=self.kperm)(self.pstate)

class CostPermute:
    u'returns the "cost" of translations due to permutation of oligo peaks'
    perm = tuple() # type: Tuple[int, ...]
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


class ScoredKPerm:
    u'''
    simple container for scores, and associated data.OligoPeakKPerm
    '''
    kperm=data.OligoPeakKPerm() # type: data.OligoPeakKPerm
    pdfcost=0.0 # type: float
    noverlaps=-1 # type: int
    @initdefaults(frozenset(locals()))
    def __init__(self,**kwa):
        pass

    def intersect_with(self,other):
        u'returns true if any oligo in kperm can be found in other'
        return set(self.kperm.kperm).intersection(set(other.kperm.kperm))!=set()

    @classmethod
    def add(cls,*args):
        u'''
        combine kperms and scores
        if keeping track of outer_seqs
        we can combine pdfcost by multiplication
        and noverlaps by addition
        '''
        if len(args)==1:
            return args[0]

        res=cls.__add2(*args[:2])
        for sckp in args[2:]:
            res = cls.__add2(res,sckp)
        return res

    @classmethod
    def __add2(cls,first,second):
        u'combine kperms and density scores'
        kperm=data.OligoPeakKPerm.add(first.kperm,second.kperm)
        pdfcost=-first.pdfcost*second.pdfcost
        noverlaps=first.noverlaps+second.noverlaps
        return cls(kperm=kperm,pdfcost=pdfcost,noverlaps=noverlaps)

    def __mul__(self,other):
        return self.__add2(self,other)

class ScoreAssembly:
    u'''
    given an assembly (list of oligos in the correct order)
    returns (number of overlaps,cost of permutation)
    '''
    kperm=data.OligoPeakKPerm() # type: data.OligoPeakKPerm
    ooverl=-1 # type: int
    @initdefaults
    def __init__(self,**kwa):
        pass

    def run(self)->ScoredKPerm:
        u'compute score'
        return ScoredKPerm(kperm=self.kperm,
                           pdfcost=self.density(),
                           noverlaps=self.noverlaps())

    def density(self,attr="kperm")->float:
        u'''
        density must take into account all peaks in kperm (or perm)
        to compute the pdfcost of neutral kperms (mandatory)
        the pdfcost of 2 kperm are comparable iff set(kperm) are the same
        '''
        return OptiKPerm(kperm=getattr(self.kperm,attr)).cost()

    def noverlaps(self)->int: # to check
        u'''
        returns the number of consecutive overlaps between oligos in kpermids
        '''
        kperm=self.kperm.kperm
        return len([idx for idx,val in enumerate(kperm[1:])
                    if len(data.Oligo.tail_overlap(kperm[idx].seq,
                                                   val.seq))==self.ooverl])

    def __call__(self,kperm:data.OligoPeakKPerm)->ScoredKPerm:
        self.kperm=kperm
        return self.run()

class ScoredKPermCollection:
    u'''
    handles a list of ScoredKPerm
    '''

    def __init__(self,sckperms:List[ScoredKPerm])->None:
        self.sckperms=sckperms

    @classmethod
    def product(cls,*args):
        u'''
        returns the product of any 2 elements in 2 different ScoredKPermCollection
        '''
        if len(args)==1:
            return args[0]

        res = cls.__product2(*args[:2])
        for sckpm in args[2:]:
            res = cls.__product2(res,sckpm)
        return res

    @classmethod
    def __product2(cls,first,second):
        u'returns  the product of 2 ScoredKPermCollection'
        sckpm=list(ScoredKPerm.add(*prd)
                   for prd in itertools.product(first.sckperms,second.sckperms))
        return cls(sckperms=sckpm)

    def compute_noverlaps(self,score:ScoreAssembly)->None:
        u'calls score on each sckperm to update noverlap valuex'
        for sckpm in self.sckperms:
            score.kperm=sckpm.kperm
            sckpm.noverlaps=score.noverlaps()

    def intersect_with(self,other):
        u'''
        returns True if any OligoPeakKPerm in self is also in other
        '''
        for sckpm in self.sckperms:
            if any(set(sckpm.kperm.kperm).intersection(set(oth.kperm.kperm))
                   for oth in other.sckperms):
                return True
        return False

    def __mul__(self,other):
        return numpy.matrix(self.sckperms).T*numpy.matrix(other.sckperms)

class ScoreFilter:
    u'''
    filter out ScoredKPerm which cannot lead to the 'best' score.
    Care must be taken when filtering kperms.
    At the moment we are considering kperms independently of the neighboring oligos
    the solution (IMPLEMENTED) would be to consider groups of kperms
    which have same outlying oligos
    '''
    scorekperms = [] # type: List[ScoredKPerm]
    __pdfthreshold = 0.0 # type: float
    ooverl=1 # type: int
    @initdefaults(frozenset(locals()))
    def __init__(self,**kwa):
        pass

    def __call__(self,sckperms):
        u'''
        functor calls run
        '''
        self.scorekperms = sckperms
        return self.run()

    def __filter1(self,scorekperms)->List[ScoredKPerm]:
        u'''
        implements minimal condition for optimal score
        for the same value of overlaps, filters out
        the scores with pdfcost > lower(pdfcost)*(1-__pdfthreshold)
        '''
        out = [] # type: List[ScoredKPerm]
        sorted_sckp= sorted(scorekperms,key=lambda x:x.noverlaps)

        for group in itertools.groupby(sorted_sckp,lambda x:x.noverlaps):
            sgroup = sorted(group[1],key=lambda x:x.pdfcost)
            minpdf = sgroup[0].pdfcost*(1-self.__pdfthreshold)
            out+=[sgroup[0]]
            out+=[grp for grp in sgroup[1:] if grp.pdfcost<minpdf]
        return out


    def __filter2(self,scorekperms)->List[ScoredKPerm]: # pylint: disable=no-self-use
        u'''
        discard solutions with higher pdfcost and fewer noverlaps
        '''
        return [sckp for sckp in scorekperms
                if len([i for i in scorekperms
                        if i.noverlaps>sckp.noverlaps
                        and i.pdfcost<sckp.pdfcost])==0]

    def run(self)->List[ScoredKPerm]:
        u'runs filters in turn'
        # group scorekperms by kperms with same outlying sequence
        # this will work for kpermids which are connex.. needs to be more general
        outseqs=set(sckp.kperm.outer_seqs(self.ooverl) for sckp in self.scorekperms)
        groups = [[sckp for sckp in self.scorekperms
                   if sckp.kperm.outer_seqs(self.ooverl)==out]
                  for out in outseqs]
        filtered=[] # type: List[ScoredKPerm]
        for group in groups:
            grp=self.__filter1(group)
            grp=self.__filter2(grp)
            filtered+=grp
        return filtered
