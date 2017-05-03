#!/usr/bin/env python3
# -*- coding: utf-8 -*-

u'''
regroups functions and classes to complement assembler
'''
import math
import itertools
from typing import List, Tuple, Set, Callable, NamedTuple # pylint: disable=unused-import
import pickle
import scipy
import numpy
from utils.logconfig import getLogger
from utils import initdefaults

from . import data
from ._types import SciDist # pylint: disable=unused-import

LOGS = getLogger(__name__)

OliBat = NamedTuple("OliBat",[("oli",data.OligoPeak),
                              ("idinbat",int),
                              ("batid",int)])

class OptiDistPerm:
    u'''
    optimize translational cost of permutation
    '''
    perm = (-1,) # type: Tuple[int]
    dists = [] # type: List[SciDist]
    @initdefaults()
    def __init__(self,**kwa):
        pass

    @property
    def _epsi(self)->float:
        try:
            return self._epsi
        except AttributeError:
            self.__setattr__("_epsi",0.001*min([self.dists[i].std() for i in self.perm]))
        return self._epsi

    def run(self)->numpy.ndarray:
        u'returns the PERMUTATED state which maximise the probability'
        constraints = []
        for idx in range(len(self.perm[:-1])):
            constraints.append({"type":"ineq",
                                "fun":SOMConstraint(index=idx,_epsi=self._epsi)})

        xinit = [self.dists[i].mean() for i in self.perm]
        fun = CostPermute(dists=self.dists,
                          perm=self.perm)
        return scipy.optimize.minimize(fun,xinit,constraints=constraints).x

class CostPermute:
    u'returns the "cost" of translations due to permutation of oligo peaks'
    perm = (-1,) # type: Tuple[int]
    dists = [] # type: List[SciDist]
    @initdefaults()
    def __init__(self,**kwa):
        pass
    def __call__(self,xstate):
        return -numpy.product([self.dists[vlp].pdf(xstate[idp])
                               for idp,vlp in enumerate(self.perm)])

class SOMConstraint:
    u'functor for scipy.optimize.minimize constraints'
    index = -1 # type: int
    _epsi = -1.0 # type: float
    @initdefaults
    def __init__(self,**kwa):
        pass
    def __call__(self,xstate):
        return xstate[self.index+1]-xstate[self.index]-self._epsi



class ComputeOSwaps:
    u'Computes possible permutation between'
    # if need to merge 2 by 2 batches, create BCollection of 2 batches?
    collection=data.BCollection() # type: data.BCollection
    nscale=1 # type: int
    ooverl=1 # type: int
    __groups=list() # type: List
    @initdefaults
    def __init__(self,**kwa):
        pass

    @property
    def oligos(self):
        u'returns the oligos in collection'
        return self.collection.oligos

    def __group_matching(self,groups:List[List[OliBat]])->List[List[OliBat]]: # to check
        u'''
        a grp is a list of tuples (oligo,oligo index, batch id)
        returns a list of list of (oligo,oligo index, batch id)
        each oligo in a list has ooverl bases with at least another oligo in the same list
        defines rule to swap n-oligos with ooverl overlapping bases
        '''
        # if two oligos are in the same batch they should at least have ooverl overlaps
        # do we put them in the same cluster?
        # yes, we compute arrangements between batches afterwards

        clusters = [] # type: List[List[OliBat]]

        for grp in groups:
            seed = set([grp[0].oli.seq[:self.ooverl],grp[0].oli.seq[-self.ooverl:]])
            seed = _update_seed(self.ooverl,seed,grp)
            pergrp = [[elmt for elmt in grp if elmt.oli.seq[:self.ooverl] in seed or\
                       elmt[0].seq[-self.ooverl:] in seed]]
            seedsingrp = set(seed)
            while sum(len(i) for i in pergrp)!=len(grp):
                # pick a new seed not in seed and restart
                seed = [set([elmt[0].seq[:self.ooverl],elmt[0].seq[-self.ooverl:]])\
                        for elmt in grp if not elmt[0].seq[:self.ooverl] in seedsingrp][0]
                seed = _update_seed(self.ooverl,seed,grp)
                pergrp+=[[elmt for elmt in grp\
                            if elmt[0].seq[:self.ooverl] in seed or\
                          elmt[0].seq[-self.ooverl:] in seed]]
                seedsingrp.update(seed)

            clusters += pergrp
        return clusters

    def compute(self)->List[List[data.OligoPeak]]:
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
        groups = self.collection.group_overlapping_batches(nscale=self.nscale)
        print("len(groups)=",len(groups))
        # move to BCollection ?
        infogrp=[]
        for grp in groups:
            info=[]
            for val in grp:
                for idx,bat in enumerate(self.collection.batches):
                    if val in bat.oligos:
                        info.append(OliBat(val,bat.oligos.index(val),idx))
                        break
            infogrp.append(info)

        LOGS.debug("before clustering, %i",len(infogrp))
        self.__groups = self.__group_matching(infogrp)
        LOGS.debug("after clustering, %i",len(self.__groups))
        # generate all arrangements between batches excluding within batch swaps

        # remove groups if there is not a representative of at least two batches
        self.__groups = [grp for grp in self.__groups if len(set(val.batid for val in grp))>1]
        print("len(self.__groups)=",len(self.__groups))
        print(sum([math.factorial(len(grp)) for grp in groups]))
        # need to carfully interpret self.__groups
        # each group in self.__groups corresponds to distinct (independent) permutations
        # we can define maps to apply on previous xstate values
        # if an oligo does not belong to the group its position remains unchanged
        with open("groups.pickle","wb") as testfile:
            pickle.dump(groups,testfile)
        with open("clusters.pickle","wb") as testfile:
            pickle.dump([grp for grp in self.__groups if len(grp)>=2],testfile)
        print(sum([math.factorial(len(grp)) for grp in self.__groups if len(grp)>=2]))

        return [grp for grp in self.__groups if len(grp)>=2]
    # oswaps = [] # type: List[data.OligoPeak]
    # for grp in self.__groups:
    #    if len(grp)<2:
    #        continue
    #    oswaps.extend(oswaps_between_batches(grp))
    # LOGS.debug("len(oswaps)=%i", len(oswaps))
    # return oswaps
    # we can parallelise computation of score over each group
    # then reassemble the sequence having the best score with no overlapping groups


def oswaps_between_batches(grp:List[OliBat])->List[data.OligoPeak]:
    # remove swaps which do not satisfy min_overl rule
    u'''
    find sequentially the possible arrangements of oligos such that:
    * at least min_overl overlapping bases between consecutive oligos
    * no arrangements between batches
    assumes that oligo indices within the batch are ordered
    '''
    bids = sorted(set(i.batid for i in grp))
    lengths = []
    for bid in  bids:
        lengths.append(len([elm for elm in grp if elm.batid==bid]))

    bybat = sorted(grp,key=lambda x:(x.batid,x.idinbat))


    combs = combinationsbetweengroups(set(range(len(grp))),
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

def combinationsbetweengroups(indices:Set[int],lengths:List[int])->List[List[int]]:
    u'''
    returns the product of combinations of size lengths
    C(lengths[0],indices)*C(lengths[1],indices)*...
    '''
    if len(lengths)==1:
        return [sorted(indices)]
    combs=[] # type: List[List[int]]
    for comb in itertools.combinations(indices,lengths[0]):
        combs+=[list(comb)+i for i in combinationsbetweengroups(indices-set(comb),lengths[1:])]

    return combs


class DefaultCallable:
    u'defines a Default Callable'
    def __init__(self,res):
        self.res=res
    def __call__(self,*args,**kwargs):
        u'returns res'
        return self.res

class ScoreGroup:
    u'''
    assigns a score to each permutation of a group of oligos
    '''
    oswap = [] # type: List[data.OligoPeak]
    score = DefaultCallable(-1.0) # type: Callable
    @initdefaults()
    def __init__(self,**kwa):
        pass

    def run(self)->List: # too long?
        u'returns (score,permutation)'
        return [(self.score(it),it) for it in itertools.permutations(self.oswap)]

class BestScoreAssemble:
    u'''
    finds the best group of non overlapping oswaps
    with best (minimal) score
    '''
    oswaps = [] # type: List[data.OligoPeak]
    # score between group
    bg_score = DefaultCallable(-1.0) # type: Callable
    # score within group
    wg_score = DefaultCallable(-1.0) # type: Callable
    __wg_scores = [] # type: List
    assemble_grps=None # type:
    @initdefaults()
    def __init__(self,**kwa):
        pass

    @property
    def scoregroups(self)->List[ScoreGroup]:
        u'returns ScoreGroup objects from oswaps'
        if hasattr(self,"scoregroups"):
            return self.scoregroups
        setattr(self,"scoregroups",
                [ScoreGroup(oswap=oswap,
                            score=self.wg_score) for oswap in self.oswaps])
        return self.scoregroups

    def compute_wg_scores(self)->None: # multiprocess?
        u'apply run to all scoregroups'
        self.__wg_scores=[sgrp.run() for sgrp in self.scoregroups]

    def compute_bg_scores(self)->None:
        u'to implement'
        pass

    def assemble(self):
        u'to implement'
        pass


class AssembleProcess:
    u'specifies rules to assemble groups of permutable oligos'
    pass
