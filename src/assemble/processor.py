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

    def compute(self)->Generator:
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
                yield [self.oligos[i] for i in permid]


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
        for prm in generate_fixedkpermids(kval,permids):
            yield prm

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

        seqs=[oli.seq for oli in  self.oligos]
        #self.overlaps={(i,j):len(data.Oligo.tail_overlap(seqs[i],seqs[j]))>=self.min_ooverl
        #               for i,j in itertools.permutations(range(len(oligos)),2)}
        # test
        self.overlaps={(i,j):len(data.Oligo.tail_overlap(seqs[i],seqs[j],shift=1))>=self.min_ooverl
                       for i,j in itertools.permutations(range(len(oligos)),2)}

    # this call is long to execute
    def __call__(self,permids:Tuple[int,...])->bool:
        'if indices of oligos is permuted checks that there is overlap'
        for idx,val in enumerate(permids[1:]):
            if permids[idx]>val:
                if not self.overlaps[(permids[idx],permids[idx+1])]:
                    if idx==0:
                        return False
                    if not self.overlaps[(permids[idx-1],permids[idx])]:
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

# finish implementation
class UpdateOligoBPos:
    u'''
    Estimates the new values of bpos for each oligo given a list of permuted oligos
    or a collection and a list of permuted indices (permids)
    '''
    oligos=[] # type: List[data.OligoPeak]
    collection=data.BCollection() # type: data.BCollection
    @initdefaults(frozenset(locals()))
    def __init__(self,**kwa):
        pass

    def __call__(self,permids=None):
        if permids is None:
            # compute bpos from the list of permuted oligos, oligos
            return self.oligos
        # compute bpos from collection and permuted indices
        return self.collection.oligos
