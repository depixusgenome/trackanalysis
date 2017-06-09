#!/usr/bin/env python3
# -*- coding: utf-8 -*-

u'''
regroups functions and classes to complement assembler
'''
import itertools
from typing import List, Tuple, Dict, Set, Callable, Any, Generator # pylint: disable=unused-import
#import pickle
import numpy
from utils.logconfig import getLogger
from utils import initdefaults

from . import data
from . import scores
from . import _utils as utils
from ._types import SciDist # pylint: disable=unused-import

LOGS = getLogger(__name__)

# to avoid mem shortage use generators instead of calling rm_notokperm earlier in the code
class ComputeOPerms:
    u'Computes possible k-permutations between oligos'
    # if need to merge 2 by 2 batches, create BCollection of 2 batches?
    collection=data.BCollection() # type: data.BCollection
    nscale=1 # type: int
    ooverl=1 # type: int
    __groups=list() # type: List
    __sort_by="pos" # non id permutation result in non ordered oligos by "pos" attr
    kmax=8 # maximal number of simultaneous permutations
    @initdefaults(frozenset(locals()))
    def __init__(self,**kwa):
        pass

    @property
    def oligos(self):
        u'returns the oligos in collection'
        return self.collection.oligos

    def __isokperm(self,perm):
        return all((getattr(perm[oid],self.__sort_by)<getattr(oli,self.__sort_by))|\
                   (perm[oid].seq[-self.ooverl:]==oli.seq[:self.ooverl])
                   for oid,oli in enumerate(perm[1:]))

    def rm_notokperm(self,perms:List[data.OligoPeak]):
        u'''discard permutations if exchanging the position of peaks
        does not result in a good sequence overlap'''
        return list(filter(self.__isokperm,perms))

    # generates duplicates when adding contribution to each group in groups?
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

        clusters = [] # type: List[List[data.OliBat]] # previously
        #clusters = {} # type: Dict
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

            clusters += pergrp # previously
            #clusters += [pgrp for pgrp in pergrp if len(pgrp)>1]
            #clusters.update(tuple(sorted(pergrp,key=lambda x:(x.batid,x.idinbat))))

        return list(clusters)

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

        # infogrp is a List[List[OliBat]]
        LOGS.debug("before clustering, %i",len(infogrp))
        # generates duplicates
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

        # self.__groups is List[List[data.OliBat]]
        # now I need to find permutation between batches and keep the permutation
        # if the permutation is ok.
        # call self.swapsbetweengroups2

        # the following a list of iterators.
        operms=map(operms_between_batches, self.__groups) # (mem pb)
        return [self.rm_notokperm(perms) for perms in operms] # (mem pb)

    def update_seed(self,seed,group:List[int]):
        u'add sequences which may overlap between elements in group'
        nseed = 0
        while nseed!=len(seed):
            nseed=len(seed)
            for elmt in group[1:]:
                if self.oligos[elmt].seq[:self.ooverl] in seed:
                    seed.update([self.oligos[elmt].seq[:self.ooverl],
                                 self.oligos[elmt].seq[-self.ooverl:]])
                    continue
                if self.oligos[elmt].seq[-self.ooverl:] in seed:
                    seed.update([self.oligos[elmt].seq[:self.ooverl],
                                 self.oligos[elmt].seq[-self.ooverl:]])
                    continue
        return seed

    def matching_group(self,groups:List[List[int]])->List[List[int]]: # to check
        u'''
        returns groups of oligos indices that which can overlap
        '''
        # if two oligos are in the same batch they should at least have ooverl overlaps
        # do we put them in the same cluster?
        # yes, we compute arrangements between batches afterwards

        clusters = [] # type: List[List[data.OliBat]] # previously
        for grp in groups:
            seed = set([self.oligos[grp[0]].seq[:self.ooverl],
                        self.oligos[grp[0]].seq[-self.ooverl:]])
            seed = self.update_seed(seed,grp)
            pergrp = [[elmt for elmt in grp if self.oligos[elmt].seq[:self.ooverl] in seed or\
                       self.oligos[elmt].seq[-self.ooverl:] in seed]]
            seedsingrp = set(seed)
            while sum(len(i) for i in pergrp)!=len(grp):
                # pick a new seed not in seed and restart
                seed = [set([self.oligos[elmt].seq[:self.ooverl]
                             ,self.oligos[elmt].seq[-self.ooverl:]])
                        for elmt in grp
                        if not self.oligos[elmt].seq[:self.ooverl] in seedsingrp][0]
                seed = self.update_seed(seed,grp)
                pergrp+=[[elmt for elmt in grp if self.oligos[elmt].seq[:self.ooverl] in seed or\
                       self.oligos[elmt].seq[-self.ooverl:] in seed]]

                seedsingrp.update(seed)

            clusters += pergrp
        return list(clusters)

    def test_compute(self)->Generator:
        u'''
        newer version of compute
        '''
        # groups indices of oligos which may overlap
        groups = utils.group_overlapping_normdists([oli.dist for oli in self.oligos],
                                                   nscale=self.nscale)[1]

        groups = self.matching_group(groups) # not sure how useful this is
        idsperbatch=self.collection.idsperbatch
        batchfilter=BetweenBatchFilter(idsperbatch=idsperbatch)
        ooverlfilter=RequireOverlapFilter(oligos=self.oligos,
                                          min_ooverl=self.ooverl)
        for grp in groups:
            # compute all possible permutations # brute force
            permids=itertools.permutations(grp) # generator
            firstfiltered = filter(ooverlfilter,permids) # type: ignore
            secondfiltered = filter(batchfilter,firstfiltered) # type: ignore

            for permid in secondfiltered:
                yield permid

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
    print("about to call swaps2combs")
    combs = swaps2combs(swapsbetweengroups(set(range(len(grp))),
                                           lengths=lengths))
    print("about to call swaps2combs")
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
    args = tuple() # type: Tuple
    kwargs = dict() # type: Dict
    #score = scores.OptiKPerm # type: ignore

    @initdefaults(frozenset(locals()))
    def __init__(self,**kwa):
        pass

    def run(self)->Tuple[float]:
        u'''
        returns a Tuple of (score0,score1,...)
        '''
        value = self.score(self.kperm)
        if callable(value):
            return value(*self.args,**self.kwargs)
        return value

class BestScoreAssemble:
    u'''
    finds the best group of non overlapping operms
    with best (minimal) score
    '''
    # operms are possibly kpermutations of oligos
    operms = [] # type: List[data.OligoPeak]
    # score between group
    score = scores.DefaultCallable(-1.0) # type: ignore
    assemblies = set() # type: Set[data.OligoPeak]
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

def ncycle2perm(cycle)->Tuple[int, ...]:
    u'converts n-cycle into permutation of size n'
    toperm={idx:val for idx,val in enumerate(cycle)}
    return tuple(toperm[idx] for idx in range(len(cycle)))

def nonid_kperms(size)->numpy.array:
    u'''
    return the non neutral cyclic permutations of elements in  range(size)
    '''
    if size>3:
        raise NotImplementedError
    cycles = ([0]+list(i) for i in itertools.permutations(range(1,size)))
    addprm = ([size-1]+list(i)+[0] for i in itertools.permutations(range(1,size-1)))
    for i in cycles:
        yield ncycle2perm(i)
    for i in addprm:
        yield i

def generate_fixedkpermids(kvalue,permids:List[int]):
    u'''
    generate only k-permutations
    returns an iterator of indices
    '''
    # for kvalue=2 (1,0) perm to apply to all indices
    # for kvalue=3 (2,0,1) and (1,2,0) to apply to all indices
    if kvalue==0:
        yield permids
    for kprm in nonid_kperms(kvalue):
        # apply kprm for each i in range(len(permids))
        for i in range(len(permids)-kvalue+1):
            yield permids[:i]+list(kprm+i)+permids[i+kvalue:]
    return

def generate_kpermids(kmin,kmax,permids:List[int]):
    u'''
    generate all k-permutations with values between kmin (incuded) and kmax (excluded)
    '''
    for kval in range(kmin,kmax):
        for permids in generate_fixedkpermids(kval,permids):
            yield permids

class BetweenBatchFilter:
    u'''
    functor
    filters out the permutation which permutes the position of OligoPeaks from the same batch
    lists in idsperbatch are supposed sorted
    '''
    def __init__(self,idsperbatch:Dict[int,List[int]])->None:
        u'''
        initiates the filter
        idsperbatch[i] =[ids of elements which must not be swap]
        '''
        self.idsperbatch=idsperbatch

    def __call__(self,permids:Tuple[int, ...]):
        for batch in self.idsperbatch.values():
            # compare the two next lines
            check=[i for i in permids if i in batch]
            #check=[list(permids).index(i) for i in batch]
            if any(check[idx]>val for idx,val in enumerate(check[1:])):
                return False
        return True


class RequireOverlapFilter:
    u'''
    functor
    filters out permutations if the permutations does not lead
    to minimal overlap between swapped OligoPeaks
    '''
    def __init__(self,oligos:List[data.OligoPeak],min_ooverl)->None:
        self.oligos=oligos
        self.min_ooverl=min_ooverl

    def __call__(self,permids:List[int]):
        u'''
        permids are the indices of the oligos
        '''
        for idx,val in enumerate(permids[1:]):
            if permids[idx]>val:
                if len(data.OligoPeak.tail_overlap(
                        self.oligos[permids[idx]].seq,
                        self.oligos[val].seq))<self.min_ooverl:
                    return False
        return True


class EXAMPLEFindValidPerms:
    u'example (not finished) way to generate valid permutation'
    def __init__(self,oligos:List[data.OligoPeak],
                 min_ooverl:int,
                 kmax:int)->None:
        self.oligos=oligos
        self.min_ooverl=min_ooverl
        self.kmax=kmax

    def run(self):
        u'''
        computes the permutations
        '''
        permids=generate_kpermids(kmin=0,
                                  kmax=self.kmax,
                                  permids=list(range(self.oligos)))
        idsperbatch=[]
        batchfilter=BetweenBatchFilter(idsperbatch=idsperbatch)
        ooverlfilter=RequireOverlapFilter(oligos=self.oligos,
                                          min_ooverl=self.min_ooverl)
        bfiltered = filter(batchfilter,permids)
        oofiltered = filter(ooverlfilter,bfiltered)
        return oofiltered # list of?
