#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u'''
defines a list of scoring functors for sequence assembly
'''
from typing import Tuple, List, NamedTuple, Set # pylint: disable=unused-import
import itertools
import numpy as np

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
    epsi=1.1 # type:float
    @initdefaults(frozenset(locals()))
    def __init__(self,**kwa):
        u'init'
        pass

    def find_subs(self):
        u'find sub-kpermutations (cyclic notation) within the permutation'
        # compute the new positions for each sub-kperm
        srtprm=sorted(self.perm)
        subkprms=[]
        for val in srtprm:
            kpr=[val]
            if self.perm[srtprm.index(val)]==kpr[0]:
                subkprms.append(tuple(kpr))
                continue
            kpr.append(self.perm[srtprm.index(val)])
            while kpr[-1]!=kpr[0]:
                kpr.append(self.perm[srtprm.index(kpr[-1])])
            subkprms.append(tuple(sorted(kpr[:-1])))
        return list(frozenset(subkprms))

    def run(self):
        u'returns sorted position with minimal pdfcost'
        subs=self.find_subs()
        perm_xs=[]
        srtprm=sorted(self.perm)
        for sub in subs:
            subdists=[self.dists[srtprm.index(i)] for i in sub]
            locscalef=sum([i.mean()/i.std()**2 for i in subdists])
            scalef=sum([1/i.std()**2 for i in subdists])
            # x intersection of gaussians
            xopt=locscalef/scalef
            perm_x=np.array([i*self.epsi for i in sub])
            perm_x=perm_x-np.mean(perm_x)+xopt
            perm_xs.extend(perm_x)

        return sorted(perm_xs)

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
        return -np.product([self.get_dists[vlp].pdf(xstate[idp])
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
        return -np.product([self.get_dists[idp].pdf(val)
                            for idp,val in enumerate(xstate)])
# needed
class ScoredPerm:
    u'''
    simple container for scores, and associated data.OligoPerm
    '''
    perm=data.OligoPerm() # type: data.OligoPerm
    pdfcost=0.0 # type: float
    noverlaps=-1 # type: int

    @initdefaults(frozenset(locals()))
    def __init__(self,**kwa):
        pass

    # not used, to remove
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

        res=cls.__add2(args[0],args[1])
        for sckp in args[2:]:
            res = cls.__add2(res,sckp)
        return res

    # not used, to remove
    @classmethod
    def __add2(cls,first,second):
        u'combine kperms and density scores'
        perm=data.OligoPerm.add(first.perm,second.perm)
        pdfcost=-first.pdfcost*second.pdfcost
        noverlaps=first.noverlaps+second.noverlaps
        return ScoredPerm(perm=perm,
                          pdfcost=pdfcost,
                          noverlaps=noverlaps)

# scores OligoKPerm
class ScoreAssembly:
    u'''
    given an assembly (list of oligos in the correct order)
    returns (number of overlaps,cost of permutation)
    '''
    perm=data.OligoPerm() # type: data.OligoPeakKPerm
    ooverl=-1 # type: int
    @initdefaults(frozenset(locals()))
    def __init__(self,**kwa):
        pass

    def run(self)->ScoredPerm:
        u'compute score'
        return ScoredPerm(perm=self.perm,
                          pdfcost=self.density(),
                          noverlaps=self.noverlaps())

    def density(self,attr="kperm")->float:
        u'''
        density must take into account all peaks in kperm (or perm)
        to compute the pdfcost of neutral kperms (mandatory)
        the pdfcost of 2 kperm are comparable iff set(kperm) are the same
        '''
        return OptiKPerm(kperm=getattr(self.perm,attr)).cost()

    def noverlaps(self,attr="kperm")->int:
        u'''
        returns the number of consecutive overlaps between oligos in kpermids
        '''
        kperm=getattr(self.perm,attr)
        return len([idx for idx,val in enumerate(kperm[1:])
                    if len(data.Oligo.tail_overlap(kperm[idx].seq,
                                                   val.seq))==self.ooverl])

    def __call__(self,kperm:data.OligoKPerm)->ScoredPerm:
        u'kperm is a k-permutation (not a more general OligoPerm)'
        try:
            getattr(kperm,"kperm")
        except AttributeError:
            raise AttributeError("ScoreAssembly needs kperm attribute")
        self.perm=kperm
        return self.run()

class LScPerm:
    u'''
    lighter version of ScoredPermCollection
    contains only pdfcost, noverlaps and permids
    '''
    pdfcost=0.0 # type: float
    noverlaps=-1 # type: int
    permids=[] # type: List[int]
    domain=set() # type: Set[int]
    @initdefaults(frozenset(locals()))
    def __init__(self,**kwa):
        pass

    def __hash__(self)->int:
        return hash((tuple(sorted(self.domain)),tuple(self.permids)))

    @classmethod
    def product(cls,*args):
        u'''
        returns the product of any 2 elements in 2 different ScoredPermCollection
        '''
        if len(args)==1:
            return args[0]

        #res = cls.__product2(*args[:2])
        res = cls.__product2(args[0],args[1])
        for sckpm in args[2:]:
            res = cls.__product2(res,sckpm)
        return res

    @classmethod
    def __product2(cls,first,second):
        return LScPerm(permids=np.array(first.permids)[second.permids],
                       domain=first.domain.union(second.domain),
                       pdfcost=-first.pdfcost*second.pdfcost,
                       noverlaps=first.noverlaps+second.noverlaps)


class LScPermCollection:
    u'''
    lighter version of ScoredPermCollection
    used to merged large collections together
    oligo seqs and perms information is lost but can be recovered
    '''
    def __init__(self,scperms:List[LScPerm])->None:
        u'init'
        self.scperms=scperms

    @classmethod
    def product(cls,*args):
        u'''
        returns the product of any 2 elements in 2 different ScoredPermCollection
        '''
        if len(args)==1:
            return args[0]

        #res = cls.__product2(*args[:2])
        res = cls.__product2(args[0],args[1])
        for sckpm in args[2:]:
            res = cls.__product2(res,sckpm)
        return res

    @classmethod
    def __product2(cls,collection1,collection2):
        u'product of 2 LScPermCollections'
        if __debug__:
            if collection1.intersect_with(collection2):
                print(collection1.scperms[0].domain)
                print(collection2.scperms[0].domain)
                print("pb the 2 permutations are not independant")
        perms1=np.matrix([i.permids for i in collection1.scperms])
        perms2=np.matrix([i.permids for i in collection2.scperms])
        merged_permids=perms1[:,perms2]
        merged_pdfcost=-np.matrix([i.pdfcost for i in collection1.scperms]).T*np.matrix\
            ([i.pdfcost for i in collection2.scperms])
        merged_noverlaps=np.matrix([i.noverlaps for i in collection1.scperms]).T\
                          +np.matrix([i.noverlaps for i in collection2.scperms])

        scores=[LScPerm(pdfcost=merged_pdfcost[i1,i2],
                        noverlaps=merged_noverlaps[i1,i2],
                        domain=collection1.scperms[i1].\
                        domain.union(collection2.scperms[i2].domain),
                        permids=merged_permids[i1,i2,:].\
                        reshape((1,perms2.shape[1])).tolist()[0])
                for i1 in range(len(collection1.scperms))
                for i2 in range(len(collection2.scperms))]

        return LScPermCollection(scperms=scores)

    def intersect_with(self,other):
        u'''
        returns True if any OligoPerm in self is also in other
        '''
        for scpm in self.scperms:
            if any(scpm.domain.intersection(oth.domain)
                   for oth in other.scperms):
                return True
        return False

class ScoreFilter:
    u'''
    filter out ScoredPerm which cannot lead to the 'best' score.
    works only on OligoKPerms
    by construction of OligoPerms from OligoKPerms ScoreFilter is useless
    '''
    scoreperms = [] # type: List[ScoredPerm]
    __pdfthreshold = 0.0 # type: float
    ooverl=1 # type: int
    @initdefaults(frozenset(locals()))
    def __init__(self,**kwa):
        pass

    def __call__(self,scperms):
        u'''
        apply reduction on collection of permutations
        each collection are assumed to have the same domain
        '''
        self.scoreperms = scperms
        return self.run()

    def _filter1(self,scorekperms)->List[ScoredPerm]:
        u'''
        implements minimal condition for optimal score
        for the same value of overlaps, filters out
        the scores with pdfcost > lower(pdfcost)*(1-__pdfthreshold)
        '''
        out = [] # type: List[ScoredPerm]
        sorted_sckp= sorted(scorekperms,key=lambda x:x.noverlaps)

        for group in itertools.groupby(sorted_sckp,lambda x:x.noverlaps):
            sgroup = sorted(group[1],key=lambda x:x.pdfcost)
            minpdf = sgroup[0].pdfcost*(1-self.__pdfthreshold)
            out+=[sgroup[0]]
            out+=[grp for grp in sgroup[1:] if grp.pdfcost<minpdf]
        return out


    def _filter2(self,scoreperms)->List[ScoredPerm]: # pylint: disable=no-self-use
        u'''
        discard solutions with higher pdfcost and fewer noverlaps
        '''
        return [scp for scp in scoreperms
                if len([i for i in scoreperms
                        if i.noverlaps>scp.noverlaps
                        and i.pdfcost<scp.pdfcost])==0]

    def run(self)->List[ScoredPerm]:
        u'runs filters in turn'
        outseqs=set(scp.perm.outer_seqs(self.ooverl) for scp in self.scoreperms)
        groups = [[scp for scp in self.scoreperms
                   if scp.perm.outer_seqs(self.ooverl)==out]
                  for out in outseqs]
        filtered=[] # type: List[ScoredPerm]
        for group in groups:
            grp=self._filter1(group)
            grp=self._filter2(grp)
            filtered+=grp
        return filtered



# to score a partition need to list all paths
# each path is a list of OligoKperms
# add all OligoKperms
