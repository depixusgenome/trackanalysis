#!/usr/bin/env python3
# -*- coding: utf-8 -*-

u'''
regroups functions and classes to complement assembler
'''
import itertools
from typing import List, Tuple, Set, Callable, Any # pylint: disable=unused-import
import numpy
from utils.logconfig import getLogger
from utils import initdefaults

from . import data
from . import scores
from ._types import SciDist # pylint: disable=unused-import

LOGS = getLogger(__name__)

class ComputeOPerms:
    u'Computes possible permutation between oligos'
    # if need to merge 2 by 2 batches, create BCollection of 2 batches?
    collection=data.BCollection() # type: data.BCollection
    nscale=1 # type: int
    ooverl=1 # type: int
    __groups=list() # type: List
    @initdefaults(frozenset(locals()))
    def __init__(self,**kwa):
        pass

    @property
    def oligos(self):
        u'returns the oligos in collection'
        return self.collection.oligos

    def __group_matching(self,groups:List[List[data.OliBat]])->List[List[data.OliBat]]: # to check
        u'''
        a grp is a list of tuples (oligo,oligo index, batch id)
        returns a list of list of (oligo,oligo index, batch id)
        each oligo in a list has ooverl bases with at least another oligo in the same list
        defines rule to swap n-oligos with ooverl overlapping bases
        '''
        # if two oligos are in the same batch they should at least have ooverl overlaps
        # do we put them in the same cluster?
        # yes, we compute arrangements between batches afterwards

        clusters = [] # type: List[List[data.OliBat]]

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
        u'''
        returns a list of k-permutations of oligos
        the idea is to reduce the number of arrangements to the minimum.
        2 assumptions :

            * oligos may swap positions if they are within 2 nscale from one another
            * consecutive oligos must have overlap by ooverl bases

            1. group oligos which may swap due to measurement error
            2. within each group in (1), cluster oligos if they overlap with osize-1 bases
            3. compute all combinations of arrangements between batches within each cluster
            4. to do: not all arrangements between batches should be allowed
                need to discard those which do not have ooverl bases
                -> just use brute force. to discard arrangements
            5. returns the full list of arrangements to consider
        '''
        groups = self.collection.group_overlapping_batches(nscale=self.nscale)
        # move to BCollection ?
        infogrp=[]
        for grp in groups:
            info=[]
            for val in grp:
                for idx,bat in enumerate(self.collection.batches):
                    if val in bat.oligos:
                        info.append(data.OliBat(val,bat.oligos.index(val),idx))
                        break
            infogrp.append(info)

        LOGS.debug("before clustering, %i",len(infogrp))
        self.__groups = self.__group_matching(infogrp)
        LOGS.debug("after clustering, %i",len(self.__groups))

        # remove groups if there is not a representative of at least two batches
        self.__groups = [grp for grp in self.__groups if len(set(val.batid for val in grp))>1]
        print("len(groups)=",len(groups))

        # need to carefuly interpret self.__groups
        # each group in self.__groups corresponds to distinct (independent) permutations
        # not quite, they are distinct iff the intersection of set of indices is empty
        # we can define maps to apply on previous xstate values
        # if an oligo does not belong to the group its position remains unchanged

        return list(map(operms_between_batches, self.__groups))
    # we can parallelise computation of score over each group
    # then reassemble the sequence having the best score with no overlapping groups


#def operms_between_batches(grp:List[data.OliBat])->Iterator[data.OligoPeak]:
# by adding attribute to grp, can easily return the permuted indices instead of oligos.
def operms_between_batches(grp):
    # remove swaps which do not satisfy min_overl rule
    u'''
    find sequentially the possible arrangements of oligos such that:
    * at least min_overl overlapping bases between consecutive oligos
    * no arrangements between batches
    assumes that oligo indices within the batch are ordered
    '''
    bids = sorted(set(i.batid for i in grp))
    lengths = []
    for bid in bids:
        lengths.append(len([elm for elm in grp if elm.batid==bid]))

    def func(arg):
        u'lambda'
        return (arg.batid,arg.idinbat)
    bybat = sorted(grp,key=func)
    olibybat = numpy.array([i.oli for i in bybat])
    combs = swaps2combs(swapsbetweengroups(set(range(len(grp))),
                                           lengths=lengths))
    return list(map(olibybat.__getitem__,combs))

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

def __tocombs(swap):
    return [i[1] for i in sorted([(v,k) for k,v in enumerate(swap)])]

def swaps2combs(swaps):
    u'reorder swaps to use as oligo[comb]'
    return list(map(__tocombs,swaps))

def swapsbetweengroups(indices:Set[int],lengths):
    # PB, creates duplicates
    # finds k-permutations
    # can be made more efficient by specifying the number of permuted indices
    # size 0, identity
    # size 1, identity
    # size 2, etc..
    u'''
    returns the new index an oligo should have
    ex : [1,2,0] then oligo 0 should go to position 1 in new order
    see swaps2combs
    C(lengths[0],indices)*C(lengths[1],indices)*...
    '''
    if len(indices)==len(lengths):
        swaps=[i for i in itertools.permutations(indices)]
    else:
        swaps=[] # List[Tuple]
        for swap in itertools.combinations(indices,lengths[0]):
            swaps+=[swap+i for i in swapsbetweengroups(indices-set(swap),lengths[1:])]
    return swaps

# k-perm is more general than perm
class ScoreKPerm:
    u'Scores a K-permutation of oligos'
    kperm=[] # type: List[data.OligoPeak]
    score = scores.DefaultCallable(-1.0) # type: ignore

    @initdefaults(frozenset(locals()))
    def __init__(self,**kwa):
        pass

    def run(self)->Tuple[float]:
        u'''
        returns a Tuple of (score0,score1,...)
        '''
        return self.score(self.kperm)

class BestScoreAssemble:
    u'''
    finds the best group of non overlapping operms
    with best (minimal) score
    '''
    operms = [] # type: List[data.OligoPeak]
    # score between group
    score = scores.DefaultCallable(-1.0) # type: ignore
    assemblies = set() # type: set[data.OligoPeak]
    @initdefaults(frozenset(locals()))
    def __init__(self,**kwa):
        pass

    def assemble_oligos(self):
        u'''
        creates all possible non overlapping permuted oligos
        '''
        # can add permutations if intersection of permuted oligo sets is empty

        # brute force impl.: underestimate of assemblies
        print("number of checks to do:",
              len(list(itertools.combinations_with_replacement([0,1],len(self.operms)))))

        # add all permutation which do not intersect

    def rank_assemblies(self): # multiprocess? no. multiprocecssing should be higher level
        u'compute score of ordered list of oligos'
        return [(self.score(asm))+(asm,) for asm in self.assemblies]
