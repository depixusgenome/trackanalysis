#!/usr/bin/env python3
# -*- coding: utf-8 -*-

u'''
given k-permutations, attempts to reconstruct the most likely order of oligohits
kperms, should (or not?) include neutral operators. Depends on the solution Searcher
'''

from typing import List, Dict, Tuple # pylint: disable=unused-import
import pickle
import itertools
import numpy
from utils import initdefaults
from .data import OligoPeakKPerm
from . import scores # needed to estimate the quality of each kperm

class KPermAssessor:
    u'''
    rank the kperms by importance (quality)
    '''
    kperms = [] # type: List[OligoPeakKPerm]
    __scorekperm=dict() # type: Dict
    __ranking=[] # type: List[Tuple]
    @initdefaults(frozenset(locals()))
    def __init__(self,**kwa):
        u'''
        oligos is the full list of oligos
        kperms is the list of k-permutations
        '''
        pass

    @property
    def scorekperm(self)->Dict:
        u'score each kperm'
        if self.__scorekperm==dict():
            self.__scorekperm={kpr:scores.ScoreAssembly(assembly=kpr.kperm).run()\
                               for kpr in self.kperms}
        return self.__scorekperm

    def scores(self)->List:
        u'apply ScoreAssembly on each of the kperms'
        return [self.scorekperm[kpr] for kpr in self.kperms]

    def ranking(self,reverse=False):
        u'returns sorted [(score,kperm) for kperm in kperms]'
        if self.__ranking==[]:
            self.__ranking=sorted(self.scorekperm.items(),reverse=reverse)
        return self.__ranking

    # must be corrected to account for changes of same size
    # changes (3,1,2) and (3,2,1) belong to the same supergroup 
    def find_supergroups(self,kperms=None,attr="changes"):
        u'''
        find kperms whose getattr(kperm,attr) is not included by any other kperm
        '''
        if kperms is None:
            kperms=list(self.kperms)
        allchanges=[set(getattr(i,attr)) for i in kperms]
        #supergroups=[i for i in kperms if not any(numpy.array(allchanges)>set(getattr(i,attr)))]
        supergroups=[i for i in kperms if not any(numpy.array(allchanges)>set(getattr(i,attr)))]
        # need to regroup same supergroups
        return supergroups

    # to check
    def find_subgroups(self,kperm:OligoPeakKPerm,attr="changes")->List[OligoPeakKPerm]:
        u'''returns the list whose attr are subgroups of kperm
        kperm is excluded from the list
        '''
        return [kprm for kprm in self.kperms if set(getattr(kperm,attr))>set(getattr(kprm,attr))]

class DownTopSearcher:
    u'combines smaller permutations first'
    kpermassessor = KPermAssessor()
    @initdefaults
    def __init__(self,**kwa):
        pass

    @classmethod
    def merge(cls,subgroups,attr="changes")->List[OligoPeakKPerm]:
        u'''
        no grp in subgroups contains any other grp
        combine groups if they do not overlap
        assumes that the kperm do not include any neutral permutations
        '''
        if len(subgroups)==1:
            return subgroups
        print("len(subgroups)=",len(subgroups))
        pickle.dump(subgroups,open("subgroups.pickle","wb"))
        merged=[]
        for ite in itertools.product([False,True],repeat=len(subgroups)):
            subs=[sgrp for idx,sgrp in enumerate(subgroups) if ite[idx]]
            if subs==[]:
                continue
            # if any subgroups such that ite==1 intersect, pass
            if any(not set(getattr(sub1,attr)).isdisjoint(set(getattr(sub2,attr)))
                   for idx1,sub1 in enumerate(subs)
                   for sub2 in subs[idx1+1:]):
                continue
            # otherwise add the set of k-permutations
            merged.append(OligoPeakKPerm.add(*subs))
        print("len(merged)=",len(merged))
        return merged

    def merge_subgroups(self,supergroup:OligoPeakKPerm)->List[OligoPeakKPerm]:
        u'''
        recursively find subgroups
        merge subgroups
        return merged subgroups
        '''
        groupings=[supergroup]
        for grp in self.kpermassessor.find_subgroups(kperm=supergroup):
            #groupings+=self.merge([subg for subg in self.kpermassessor.find_subgroups(kperm=grp)])
            for subg in self.kpermassessor.find_subgroups(kperm=grp):
                groupings+=self.merge_subgroups(subg)

        # for each group in grouping merge
        # can compute a score here for each grp in groupings
        # if the difference in scores is above a given threshold discard the groups
        print("merging=",groupings)
        return self.merge(groupings)

    def run(self):
        u'''
        find possible ways to group the kperms by merging them
        starting from smaller pemutations to bigger ones
        should not include kperms which are neutral, nor duplicated values of change
        '''
        # find supergroups
        supergroups = self.kpermassessor.find_supergroups()
        print("len(supergroups)=",len(supergroups))
        groupings=[]
        for sgrp in supergroups: # test on first index
            print("supergroup=",sgrp.changes)
            groupings.append(self.merge_subgroups(sgrp))

        return self.merge(groupings)
