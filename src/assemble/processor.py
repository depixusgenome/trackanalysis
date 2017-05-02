#!/usr/bin/env python3
# -*- coding: utf-8 -*-

u'''
regroups functions and classes to complement assembler
'''

import itertools
from typing import List # pylint: disable=unused-import
import collections
import numpy
from utils.logconfig import getLogger
from utils import initdefaults

from . import data
from ._types import SciDist

LOGS = getLogger(__name__)

OliBat = collections.namedtuple("OliBat",[oli,idinbat,batid])

class OptiDistPerm:
    u'''
    optimize translational cost of permutation
    '''
    perm:Tuple[int] = ()
    dists:List[SciDist] = []
    @initdefaults()
    def __init__(self,**kwa):
        pass

    @property
    def _epsi(self)->float:
        try: 
            return self._epsi
        except AttributeError:
            self.__setattr__("_epsi",0.001*min([dists[i].std() for i  in perm]))
        return self._epsi

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
    # if need to merge 2 by 2 batches, create BCollection of 2 batches?
    collection:BCollection=BCollection()
    nscale:int=1
    ooverl:int=1
    __groups:List=list()
    def __init__(self,**kwa):
        pass

    @property
    def oligos(self):
        return self.collection.oligos

    def __group_overlapping_oligos(self)->List[OligoPeak]:
        u'''
        returns groups of overlapping oligos
        '''
        groups = group_overlapping_normdists([oli.dist for oli in oligos],nscale=self.nscale)[1]
        return [[oligos[idx] for idx in grp] for grp in groups]

    def __group_matching(self,groups:list[OliBat])->list[OliBat]: # to check
        u'''
        a grp is a list of tuples (oligo,oligo index, batch id)
        returns a list of list of (oligo,oligo index, batch id)
        each oligo in a list has ooverl bases with at least another oligo in the same list
        defines rule to swap n-oligos with ooverl overlapping bases
        '''
        # if two oligos are in the same batch they should at least have ooverl overlaps
        # do we put them in the same cluster?
        # yes, we compute arrangements between batches afterwards

        clusters = []

        for grp in groups:
            seed = set([grp[0].oli.seq[:self.ooverl],grp[0].oli.seq[-self.ooverl:]])
            seed = _update_seed(self.ooverl,seed,grp)
            pergrp = [[elmt for elmt in grp if elmt.oli.seq[:self.ooverl] in seed or\
                       elmt[0].seq[-self.ooverl:] in seed]]
            seedsingrp = set(seed)
            while sum(len(i) for i in pergrp)!=len(grp):
                # pick a new seed not in seed and restart
                seed = [set([elmt[0].seq[:ooverl],elmt[0].seq[-ooverl:]])\
                        for elmt in grp if not elmt[0].seq[:ooverl] in seedsingrp][0]
                seed = _update_seed(ooverl,seed,grp)
                pergrp+=[[elmt for elmt in grp\
                            if elmt[0].seq[:ooverl] in seed or elmt[0].seq[-ooverl:] in seed]]
                seedsingrp.update(seed)

            clusters += pergrp
        return clusters

    def compute(self)->numpy.ndarray:
        # cf find_swaps
        # CAREFUL, misinterpretation of what this function returns.
        # the swap is the new arrangement of peak ids.
        # this returns the indices of the peaks flipped which
        # is in general different from the swap!!
        u'''
        returns the new xstates to explore
        the idea is to reduce the number of arrangements to the minimum.
        2 assumptions :
                * oligos may swap positions if they are within 2 nscale from one another
                * consecutive oligos must have overlap by ooverl bases
        (1) group oligos which may swap due to measurement error
        (2) within each group in (1), cluster oligos if they overlap with osize-1 bases
        (3) compute all combinations of arrangements between batches within each cluster
        (4) to do: not all arrangements between batches should be allowed
                   need to discard those which do not have ooverl bases
                   -> just use brute force. to discard arrangements
        (5) returns the full list of arrangements to consider
        '''
        groups = self.__group_overlapping_oligos()

        # move to BCollection 
        infogrp=[]
        for grp in groups:
            info=[]
            for val in grp:
                for idx,bat in enumerate(self.batches):
                    if val in bat.oligos:
                        info.append(OliBat(val,bat.oligos.index(val),idx))
                        break
            infogrp.append(info)

        LOGS.debug("before clustering, %i",len(infogrp))
        self.__groups = self.__group_matching(infogrp)
        LOGS.debug("after clustering, %i",len(self.groupping))
        # generate all arrangements between batches excluding within batch swaps

        # remove groups if there is not a representative of at least two batches
        self.__groups = [grp for grp in self.__groups if len(set(val[2] for val in grp))>1]

        oswaps = []
        for grp in self.__groups:
            if len(grp)<2:
                continue
            grposwaps = _groupswaps_between_batches(grp)
            oswaps.extend(grposwaps)

        LOGS.debug("len(oswaps)=%i", len(oswaps))
        # translate oswaps to xstates
            
        return swaps

        
def _group_overlapping_normdists(dists,nscale=1): # to pytest !! # what if no intersection?
    u'''
    returns lists of indices [(i,j,k)] each element of the tuple has distribution which overlap
    '''
    sdists=[(di.mean(),di.mean()-nscale*di.std(),di.mean()+nscale*di.std(),idx)\
            for idx,di in enumerate(dists)]
    sdists.sort()
    bounds = [(di.mean()-nscale*di.std(),idx) for idx,di in enumerate(dists)]
    bounds+= [(di.mean()+nscale*di.std(),idx) for idx,di in enumerate(dists)]
    bounds.sort()
    overlaps=[]
    for regid in range(len(bounds[:-1])):
        beflag = set(idx[1] for idx in bounds[:regid+1])
        aflag = set(idx[1] for idx in bounds[regid+1:])
        overlaps.append(sorted(beflag.intersection(aflag)))

    ssets = [set(overl) for overl in overlaps if len(overl)>1]
    ssets.sort(reverse=True)
    if len(ssets)==0:
        return ssets,[]
    uset=[ssets[0]]
    for val in ssets[1:]:
        if val.issubset(uset[-1]):
            continue
        uset.append(val)
    return ssets,uset



# returns number of arrangements to explore, considering only:
#    * arrangements between batches
#    * arrangements between oligos if overlap between oligos is osize-1
# can create a grp object to avoid confusion with regard to the order of the elements in the tuple

def _groupswaps_between_batches(grp:List[OliBat]):
    # can be made more general to include simultaneous
    # merging of more than 2 batches (when necessary)
    # remove swaps which do not satisfy min_overl rule
    # we can define the rules which would allow merging of more than 3-mers
    u'''
    find sequentially the possible arrangements of oligos such that:
        * at least min_overl overlapping bases between consecutive oligos
        * no arrangements between batches
    assumes that oligo indices within the batch are ordered
    '''
    bybat = dict()
    bids = sorted(set(i.batid for i in grp))
    lengths = []
    for bid in  bids:
        lengths.append(len([elm for elm in grp if elm.batid==bid]))
        
    bybat=sorted(grp,key=lambda x:(x.batid,x.idinbat))


    combs=combinationsbetweengroups(set(range(len(grp))),
                                    lengths=lengths)

    swaps = [sorted(zip(comb,bybat),key=lambda x:x[0]) for comb in combs]

    return [[swp[1].oli for swp in swap] for swap in swaps]

def _update_seed(ooverl,seed,grp):
    nseed = 0
    while nseed!=len(seed):
        nseed=len(seed)
        for elmt in grp[1:]:
            if elmt[0].seq[:ooverl] in seed:
                seed.update([elmt[0].seq[:ooverl],elmt[0].seq[-ooverl:]])
                continue
            if elmt[0].seq[-ooverl:] in seed:
                seed.update([elmt[0].seq[:ooverl],elmt[0].seq[-ooverl:]])
                continue
    return seed


def optimal_perm_normdists(perm:List,dists:List[SciDist])->numpy.ndarray: # pytest
    u'''
    given a permutation perm and the known distributions of each state
    returns the PERMUTATED state which maximise the probability
    '''
    assert len(perm)==len(dists)
    _epsi = 0.001*min([dists[i].std() for i  in perm])

    constraints = []
    for idx in range(len(perm[:-1])):
        constraints.append({"type":"ineq",
                            "fun":SOMConstraint(idx,_epsi)})

    xinit = [dists[i].mean() for i in perm]
    fun = CostPermute(dists,perm)
    return scipy.optimize.minimize(fun,xinit,constraints=constraints).x


def combinationsbetweengroups(indices:Set[int],lengths:List[int]):
    u'''
    returns the product of combinations of size lengths
    C(lengths[0],indices)*C(lengths[1],indices)*...
    '''
    combs=[]
    if len(lengths)==1:
        return [sorted(indices)]
    for comb in itertools.combinations(indices,lengths[0]):
        combs+=[list(comb)+i for i in combinationsbetweengroups(indices-set(comb),lengths[1:])]

    return combs
