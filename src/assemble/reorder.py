#!/usr/bin/env python3
# -*- coding: utf-8 -*-

u'''
given k-permutations, attempts to reconstruct the most likely order of oligohits
kperms, should (or not?) include neutral operators. Depends on the solution Searcher
'''

from typing import List, Dict, Set, NamedTuple, Tuple, Callable # pylint: disable=unused-import
import pickle
import itertools
import numpy
from utils import initdefaults
from . import data
from . import scores

# mostly obsolete...
class KPermAssessor:
    u'''
    rank the kperms by importance (quality)
    '''
    kperms = [] # type: List[data.OligoKPerm]
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
    def merge(cls,subgroups,attr="changes")->List[data.OligoKPerm]: # to check # no duplicates
        u'''
        no grp in subgroups contains any other grp
        combine groups if they do not overlap
        assumes that the kperm do not include any neutral permutations
        '''
        if len(subgroups)==1:
            return subgroups
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
            merged.append(data.OligoKPerm.add(*subs))
            # if len(subs)==1 the kperm is added
        print("len(merged)=",len(merged))
        return merged

    def merge_subgroups(self,supergroup:data.OligoKPerm)->List[data.OligoKPerm]:
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

    def find_subgroups(self,kperm:data.OligoKPerm,attr="changes")->List[data.OligoKPerm]:
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

    def group_perms(self,perms=None,attr="domain")->List[List[data.OligoPerm]]:
        u'''
        find perms whose getattr(kperm,attr) is not included by any other kperm
        '''
        if perms is None:
            perms=list(self.kpermassessor.kperms)
        attrsets=set(tuple(sorted(getattr(i,attr))) for i in perms)
        groups=[[perm for perm in perms if tuple(sorted(getattr(perm,attr)))==ats]
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

        possible improvements:
        * mergeable counts for each element in disjoint to part in partition
        -> duplicate on neutral k-permutation? could build a list/map/network
        where each group are 2 by 2 disjoint instead of look for 2**(disjoints groups)

        '''
        pickle.dump(list(self.kpermassessor.kperms),open("perms2group.pickle","wb"))
        # find groups of kperms (perms ?!), does it make collections of perms??
        groups = self.group_perms()

        # reversed sort groups per size
        groups = sorted(groups,key=lambda x:-len(x))

        # scored, List[List[ScoredPerm]]
        scored=[[self.scoring(prm) for prm in grp] for grp in groups]
        pickle.dump(scored,open("scored.pickle","wb"))
        scfilter = scores.ScoreFilter(ooverl=self.ooverl)
        print("before filtering",[len(grp) for grp in scored])
        filtered = [scfilter(grp) for grp in scored]

        # the partition is on the groups intersecting filtered[0] David
        # Oh, you are right. Cheers!

        # we need to discard groups of a single elements (i.e. the neutral k-permutation)
        filtered = list(filter(lambda x:len(x)>1,filtered))
        # remove collections consisting only of neutral permutations
        print("after filtering",[len(grp) for grp in filtered])
        filtered =  [scp for scp in filtered
                     if not all([len(scprm.perm.changes)==0 for scprm in scp])]
        filtered = [scores.ScoredPermCollection(scperms=grp) for grp in filtered]
        pickle.dump(filtered,open("filtered.pickle","wb"))

        # FROM THIS POINT USE LightScPermCollection instead
        divisions=self.subdivide_then_partition(filtered)
        #stop
        # for each dubdivision
        # merge each division separately
        # then merge the results together
        merged_divi=[]
        for idx,divi in enumerate(divisions):
            merged_divi.append(self.merge_division(divi))
            pickle.dump(merged_divi[-1],open("merged_divisions_backup"+str(idx)+".pickle","wb"))


        # continue from here
        # it appears that no collections in merged_division_backup.pickle intersect_with any of
        # merged_division1_backup.pickle ...
        # but it will not be a general rule!
        #merged_flat0=[lkpc[0] for lkpc in merged[0]]
        #merged_flat1=[lkpc[0] for lkpc in merged[1]]
        #full_merge=[scores.ScoredPermCollection.product(first,second)
        #for first,second in itertools.product(merged_flat0,merged_flat1)]
        #pickle.dump(full_merge,open("full_merge.pickle","wb"))
        #print(len(full_merge))

        return merged_divi


    # pylint: disable=no-self-use
    def merge_division(self,division:List[List[scores.ScoredPermCollection]]):
        u'''
        reduces the permcollection of each element in division to 1 scores.ScoredPermCollection
        before moving to the next one
        application of ScoreFilter made useless by construction of ScoredPermCollection (good)
        plus ScoreFilter should be applied to same permutation
        within a collection (i.e. same domain)
        '''
        for idx,div in enumerate(division):
            print("idx=",idx)
            if len(div)==1:
                continue
            while len(div)>1:
                print("len(div)=",len(div))
                scp1,scp2=div[:2]
                merged=scores.ScoredPermCollection.product(scp1,scp2)
                for divi in division[idx:]:
                    if scp1 in divi and scp2 in divi:
                        divi.remove(scp1)
                        divi.remove(scp2)
                        divi.append(merged)

        return division

    def subdivide_then_partition(self,
                                 collections:List[scores.ScoredPermCollection],
                                 sort_by="domain",
                                 max_size=50):
        u'''
        it is not really possible to ensure that overlapping kpc are together since
        they might be dependant 2 by 2
        args:
        max_size argument is a tricky one.
        Until find_partitions is reimplemented, max_size can struggle for too high values.
        the bigger the max_size, the fewer the partitions to merge.
        find_partitions is too long for more than 30 data.KPermCollections

        Order the data.KPermCollection
        subdivide into 30 data.KPermCollection segments
        for each subdivision compute the partitions
        for each partition, merge the data.KPermCollection
        * each subdivision will have many partition,
        ranking (deleting worse) partition should take place
        * the end result of the mergin is a new data.KPermCollection
        each kperm in the collection is a merge of multiple ones
        '''
        ocollect = tuple(sorted(collections,
                                key = lambda x:min(getattr(x.scperms[0].perm,sort_by))))
        print("len(ocollect)=",len(ocollect))
        subdivision=[tuple(ocollect[max_size*i:(i+1)*max_size])
                     for i in range(int(numpy.ceil(len(ocollect)/max_size)))]
        print("sumlentopart",sum(len(i)for i in subdivision))
        print("len of each partition ",list(len(i) for i in subdivision))
        per_subdivision=[]

        for subd in subdivision:
            partitions=[]
            seeds = [scpc for scpc in subd if scpc.intersect_with(subd[0])]
            for seed in seeds:
                partitions.extend(self.find_partitions(seed,
                                                       [scpc for scpc in subd
                                                        if not scpc.intersect_with(seed)]))
                # looking for duplicates

            per_subdivision.append(partitions)

        pickle.dump(per_subdivision,open("per_subdivision_backup.pickle","wb"))
        return per_subdivision

    # it appears that recursion is slow for python. Try a reimplementation using while loop
    def find_partitions(self,
                        part:scores.ScoredPermCollection,
                        collections:List[scores.ScoredPermCollection])\
                        ->List[List[scores.ScoredPermCollection]]:
        u'''
        part should not be in collections nor any collection which intersects with part
        recursive call
        '''
        if len(collections)==0:
            return [[part]]
        # look at each collection and see if they overlap with others
        intersections = list([i for i,v in enumerate(collections)
                              if scpc.intersect_with(v)] for scpc in collections)
        intersections = sorted(intersections,key=len,reverse=True)
        # if they only overlap with themselves, then they can all be merged
        if len(intersections[0])==1:
            return [[part]+collections]

        return [[part]+toadd
                for i in intersections[0]
                for toadd in self.find_partitions(collections[i],
                                                  [scpc for scpc in collections
                                                   if not scpc.intersect_with(collections[i])])]
