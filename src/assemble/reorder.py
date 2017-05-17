#!/usr/bin/env python3
# -*- coding: utf-8 -*-

u'''
given k-permutations, attempts to reconstruct the most likely order of oligohits
kperms, should (or not?) include neutral operators. Depends on the solution Searcher
'''

from typing import List, Dict, Tuple, Callable # pylint: disable=unused-import
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


class DownTopSearcher:
    u'''
    obsolete
    combines smaller permutations first
    '''
    kpermassessor = KPermAssessor()
    @initdefaults
    def __init__(self,**kwa):
        pass

    @classmethod
    def merge(cls,subgroups,attr="changes")->List[OligoPeakKPerm]: # to check # no duplicates
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
            subs=[sgrp for idx,sgrp in enumerate(subgroups) if ite[idx]] # filter
            if subs==[]:
                continue
            # if any subgroups such that ite==1 intersect, pass
            if any(not set(getattr(sub1,attr)).isdisjoint(set(getattr(sub2,attr)))
                   for idx1,sub1 in enumerate(subs)
                   for sub2 in subs[idx1+1:]):
                continue
            # otherwise add the set of k-permutations
            merged.append(OligoPeakKPerm.add(*subs))
            # if len(subs)==1 the kperm is added
        print("len(merged)=",len(merged))
        return merged

    def merge_subgroups(self,supergroup:OligoPeakKPerm)->List[OligoPeakKPerm]:
        u'''
        recursively find subgroups
        merge subgroups
        return merged subgroups
        '''
        groupings=[supergroup]
        for grp in self.find_subgroups(kperm=supergroup):
            #groupings+=self.merge([subg for subg in self.kpermassessor.find_subgroups(kperm=grp)])
            #for subg in self.kpermassessor.find_subgroups(kperm=grp):
            #    groupings+=self.merge_subgroups(subg)
            groupings+=self.merge_subgroups(grp)

        # for each group in grouping merge
        # can compute a score here for each grp in groupings
        # if the difference in scores is above a given threshold discard the groups
        print("merging=",[i.changes for i in groupings])
        test=self.merge(groupings)
        print("merged=",[i.changes for i in test])

        return self.merge(groupings)

    def run(self):
        u'''
        find possible ways to group the kperms by merging them
        starting from smaller pemutations to bigger ones
        should not include kperms which are neutral, nor duplicated values of change
        '''
        # find supergroups
        supergroups = self.find_supergroups()
        print("len(supergroups)=",len(supergroups))
        groupings=[]
        for sgrp in supergroups: # test on first index
            print("supergroup=",sgrp.changes)
            groupings.append(self.merge_subgroups(sgrp))

        return self.merge(groupings)

    # must be corrected to account for changes of same size
    # changes (3,1,2) and (3,2,1) do not belong to the same supergroup (required by recursion)
    def find_supergroups(self,kperms=None,attr="changes"):
        u'''
        find kperms whose getattr(kperm,attr) is not included by any other kperm
        '''
        if kperms is None:
            kperms=list(self.kpermassessor.kperms)
        allchanges=[set(getattr(i,attr)) for i in kperms]

        supergroups=[i for i in kperms
                     if not any(numpy.array(allchanges)>set(getattr(i,attr)))]

        return supergroups

    def find_subgroups(self,kperm:OligoPeakKPerm,attr="changes")->List[OligoPeakKPerm]:
        u'''
        returns the list whose attr are subgroups of kperm
        kperm must be excluded from the list for iterative purposes
        '''
        return [kprm for kprm in self.kpermassessor.kperms
                if set(getattr(kperm,attr))>set(getattr(kprm,attr))]

class KPermCombiner:
    u'''
    group kperms into bigger and independant (super)groups
    2 differents groups can only overlap partially or not at all
    Permutations can be combined between supergroups iff they do not overlap
    '''
    kpermassessor = KPermAssessor()
    scoring = lambda x: 0 # type: Callable
    @initdefaults
    def __init__(self,**kwa):
        pass

    def group_kperms(self,kperms=None,attr="kpermids")->List[List[OligoPeakKPerm]]:
        u'''
        find kperms whose getattr(kperm,attr) is not included by any other kperm
        '''
        if kperms is None:
            kperms=list(self.kpermassessor.kperms)
        attrsets=set(tuple(sorted(getattr(i,attr))) for i in kperms)
        groups=[[kperm for kperm in kperms if tuple(sorted(getattr(kperm,attr)))==ats]
                for ats in attrsets]
        return groups

    def run(self):
        u'''
        find supergroups, every possible kperm in a given supergroup is represented
        merge supergroups:
        * if they overlap entirely, they are part of the same supergroup
        * if they overlap partially, then the intersection of the supergroups should be in both
        (observed in practice)
        * if they don't overlap consider [0,0],[0,1],[1,0],[1,1], even then
        do not remove neutral permutations since :
        (1) few neutral permutations
        (2)allows neutral kperms to be ranked amongst each group
        '''
        # find groups of kperms
        groups = self.group_kperms()

        # reversed sort groups per size
        groups = sorted(groups,key=lambda x:-len(x))

        scores=[[self.scoring(kpr) for kpr in grp] for grp in groups]
        # compute score for each kperm in each group
        # remove unwanted solution :
        # for any factor such that E_tsl+factor*E_overl,
        # we know that for same values of E_overl
        # lower E_tsl values will result in worst scores
        # reduces drastically the number of combinations between groups to explore
        # for the same number of overlappings keep the kperms with lowest pdfcost (+-10 per cent)



        # reversed sort kperms by scoring value (tuple) in each group
        for grpid,grp in enumerate(groups):
            for kprid,kpr in enumerate(grp):
                print(grpid,kprid,self.scoring(kpr))



        # can analyse each group to see if any constraints are not satisfied
        # discard those solutions

        # merge all groups (2 at a time?yes)
        # merging 2 at a time we can start with the biggest group, and merge the next biggest
        # giving us len(groups[0])*len(groups[1]) solutions. (should always be manageable)
        # if kperms are ranked (better to worse (overlaps, pdfcost)) in each group
        # then we can merge solutions until

        return
