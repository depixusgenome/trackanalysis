#!/usr/bin/env python3
# -*- coding: utf-8 -*-

u'''
given k-permutations, attempts to reconstruct the most likely order of oligohits
kperms, should (or not?) include neutral operators
'''

from typing import List, Dict, Tuple # pylint: disable=unused-import
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
            self.__scorekperm=dict((kpr,scores.ScoreAssembly(assembly=kpr).run())
                                   for kpr in self.kperms)

        return self.__scorekperm

    def scores(self)->List:
        u'apply ScoreAssembly on each of the kperms'
        return [self.scorekperm[kpr] for kpr in self.kperms]

    def ranking(self,reverse=False):
        u'returns sorted [(score,kperm) for kperm in kperms]'
        if self.__ranking==[]:
            self.__ranking=sorted(self.scorekperm.items(),reverse=reverse)
        return self.__ranking

    def find_supergroups(self,kperms=None,attr="changes"):
        u'''
        find kperms whose getattr(kperm,attr) is not included by any other kperm
        '''
        if kperms is None:
            kperms=list(self.kperms)
        allchanges=[set(getattr(i,attr)) for i in kperms]
        supergroups=[i for i in kperms if not any(numpy.array(allchanges)>set(getattr(i,attr)))]
        return supergroups

    def find_subgroups(self,kperm:OligoPeakKPerm,attr="changes")->List[OligoPeakKPerm]:
        u'''returns the list whose attr are subgroups of kperm
        kperm is excluded from the list
        '''
        return [kprm for kprm in self.kperms if getattr(kperm,attr)>getattr(kprm,attr)]

class DownTopSearcher:
    u'combines smaller permutations first'
    kpermassessor = KPermAssessor()
    @initdefaults
    def __init__(self,**kwa):
        pass

    @classmethod
    def merge(cls,subgroups,attr="changes"):
        u'''
        no grp in subgroups contains any other grp
        combine groups if they do not overlap
        '''
        merged=[]
        for ite in itertools.product(*[[False,True]*len(subgroups)]):
            # if any subgroups such that ite==1 intersect, pass
            subs=[sgrp for idx,sgrp in enumerate(subgroups) if ite[idx]]
            if any(not set(getattr(sub1,attr)).isdisjoint(set(getattr(sub2,attr)))
                   for idx1,sub1 in enumerate(subs)
                   for sub2 in subs[idx1+1:]):
                continue
            # otherwise add the set of k-permutations
            merged.append(OligoPeakKPerm.add(*subs))
        return merged

    def merge_subgroups(self,supergroup:OligoPeakKPerm):
        u'''
        recursively find subgroups
        merge subgroups
        return merged subgroups
        '''
        groupings=[supergroup]
        for grp in supergroup.find_subgroups():
            groupings+=self.merge_subgroups(self.kpermassessor.find_subgroups(kperm=grp))

        # for each group in grouping merge
        # can compute a score here for each grp in groupings
        # if the difference in scores is above a given threshold discard the groups
        return self.merge(groupings)

    def run(self):
        u'''
        find possible ways to group the kperms by merging them
        starting from smaller pemutations to bigger ones
        '''
        # find supergroups
        supergroups = self.kpermassessor.find_supergroups()
        groupings=[]
        for sgrp in supergroups:
            groupings.append(self.merge_subgroups(sgrp))

        return self.merge(groupings)
