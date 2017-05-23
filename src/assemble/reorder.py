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
from .data import OligoPeakKPerm, KPermCollection
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
    ooverl=-1 # type: int
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

    @classmethod
    def __merge_kperms(cls,to_merge:List[KPermCollection])->KPermCollection:
        u'''
        merges groups of independant OligoKPerms
        '''
        # merge 2 KPermCollection at a time
        # eventually (when correct implementation of scorefilter), filter at each step
        out=KPermCollection()
        for kpc in to_merge:
            out=KPermCollection.product(out,kpc)
        return out

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


        Can we abuse the ScoreFilter?
        when the calculus of outseq wil be more general and take into account combination of
        OligoPeakKPerm then we will be able to merge groups in mergeable, 2 at a time.
        Each time a merge is performed, we could apply ScoreFilter to reduce the possible
        permutations

        possible improvements:
        * mergeable counts for each element in disjoint to part in partition
        -> duplicate on neutral k-permutation? could build a list/map/network
        where each group are 2 by 2 disjoint instead of look for 2**(disjoints groups)

        '''
        # find groups of kperms
        groups = self.group_kperms()

        # reversed sort groups per size
        groups = sorted(groups,key=lambda x:-len(x))

        scored=[[self.scoring(kpr) for kpr in grp] for grp in groups]

        scfilter = scores.ScoreFilter(ooverl=self.ooverl)
        filtered = [scfilter(grp) for grp in scored]

        pickle.dump(filtered,open("scfiltered.pickle","wb"))

        # the partition is on the groups intersecting filtered[0] David!
        # Oh, you are right. Cheers!

        # we need to discard groups of a single elements (i.e. the neutral k-permutation)
        filtered = list(filter(lambda x:len(x)>1,filtered))

        filtered = [KPermCollection(kperms=[sckp.kperm for sckp in grp]) for grp in filtered]
        # problem with filtered collections. Some are duplicated and
        # sometimes a copy of the neutral permutation
        filtered = [kpc for kpc in filtered
                    if not all([len(kpm.changes)==0 for kpm in kpc.kperms])]

        pickle.dump(filtered,open("filtered.pickle","wb"))
        partition = [kpc for kpc in filtered if kpc.intersect_with(filtered[0])]
        print("len(filtered)=",len(filtered))
        print("len(partition)=",len(partition))



        # check this loop!!
        to_merge=[]
        for part in partition:
            disjoints=[kpc for kpc in filtered if not kpc.intersect_with(part)]
            print(len(disjoints))
            mergeable = [list(itertools.compress(disjoints,comb))
                         for comb in itertools.product([True,False],repeat=len(disjoints))]
            # mergeable is a List[List[Collection]]
            # if any collection in mergeable overlap discard merge
            mergeok = [not any(kpc.intersect_with(other)
                               for idx,kpc in enumerate(merge)
                               for other in merge[idx+1:])
                       for merge in mergeable]
            to_merge.extend([[part]+ite for ite in itertools.compress(mergeable,mergeok)])
            # [part]+ite for ite in itertools.compress(mergeable,mergeok), List[collections]
        # partition # type: List[List[scorekperms]]

        pickle.dump(to_merge,open("to_merge.pickle","wb"))

        #solutions=[]
        #for grp in grpstomerge:
        #    solutions+=self.__merge_kperms(grp)
        #print("solutions=",solutions)
        # rank solutions

        # filter solutions
        # return results
        return filtered
