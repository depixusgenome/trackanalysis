#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''
permutes oligos to find maximal overlapping
checks base per base that the constructed sequence is optimal
allows for multiple possibilities
can be optimised
can be modified (1 line) # HERE to look for all suboptimal solutions
'''

import itertools
from typing import Tuple, List, Generator, Dict # pylint: disable=unused-import
import pickle
import numpy
import assemble.data as data
import assemble.scores as scores
import assemble.processor as processor
import assemble._utils as utils

# possible optimisations:

# can select a sub set of the full_kperms to construct the scaffolding

# can only check the overlap on the previous oligo in rank_by_noverlaps

# can merge partitions right after ranking so that we don't merge the first kperms each time
# if there is alternatives sequences:
# keep in memory the alternatives but resume calculation keeping (only) the common core

# can recompute segment wise the possible partitions

# must be updated to include a maximal value on the non-linearity (valve for overlapping)
# OligoPeak to far from one another may not be considered as overlapping
# must include a stretch,pos score




class Shuffler:
    u'align oligo by maximising the overlap one index at a time'
    def __init__(self,**kwa):
        self.collection=kwa.get("collection",data.BCollection()) # type:data.BCollection
        self.ooverl=kwa.get("ooverl",-1) # type: int
        self.nscale=kwa.get("nscale",1) # type: int

    @property
    def oligos(self):
        '(ordered) oligos from self.collection'
        return self.collection.oligos

    @staticmethod
    def rank_by_noverlaps(partitions:List[data.Partition],ooverl,index:int):
        '''
        to check that the score is computed on the correct index
        if we construct partitions index per index discarding those that are not optimal
        we can limit to checking that the perm[index-1:index] do overlap
        '''
        scored=[]
        for part in partitions:
            merged=part.merge()
            if __debug__:
                if not all(i in part.domain for i in range(index)):
                    print("missing index values in "+str(part.domain))
                    print("index=",index)
                    raise ValueError

            kprm=data.OligoKPerm(kperm=merged.perm[:index])

            score= scores.ScoreAssembly(perm=kprm,
                                        ooverl=ooverl)
            scored.append((score.noverlaps(),part))

        return sorted(scored,key=lambda x:x[0],reverse=True)

    @staticmethod
    def increment_noverlaps(partitions:List[data.Partition],
                            ooverl:int,
                            index:int):
        'increments the noverlaps value up to index'
        for partid,part in enumerate(partitions):
            merged=part.merge()
            if __debug__:
                if not all(i in part.domain for i in range(index)):
                    print("missing index values in "+str(part.domain))
                    print("index=",index)
                    raise ValueError


            kprm=data.OligoKPerm(kperm=merged.perm[index-2:index])

            score=scores.ScoreAssembly(perm=kprm,
                                       ooverl=ooverl)
            partitions[partid].noverlaps+=score.noverlaps()

        return

    @classmethod
    def construct_scaffold(cls,
                           base:data.Partition,
                           add_kperms:List[data.OligoKPerm],
                           index:int)->List[data.Partition]:
        '''
        the base is the starting partition is expand up to index-1
        no recursion
        '''
        if all(i in base.domain for i in range(index)):
            return [base]

        completed=[] # type: List[data.Partition]
        to_complete=[base]
        while True:
            if len(to_complete)==0:
                break
            to_add=[] # type: List[data.Partition]
            for part in to_complete:
                next_ids=[idx for idx in range(index) if not idx in part.domain]
                if len(next_ids)==0:
                    completed.append(part)
                    continue
                to_add+=[part.add(kprm,in_place=False) for kprm in add_kperms
                         if not part.domain.intersection(kprm.domain)
                         and next_ids[0] in kprm.domain]
            to_complete=to_add

        return completed

    def base_per_base(self)->List[data.Partition]:
        'constructs the sequence with maximal overlapping one base at a time'
        if __debug__:
            pickle.dump(self.oligos,open("debugoligos.pickle","wb"))

        groupedids=utils.group_overlapping_normdists([oli.dist for oli in self.oligos],
                                                     nscale=self.nscale)[1]
        if __debug__:
            pickle.dump(groupedids,open("debuggroupedids.pickle","wb"))

        full_kperms=set([]) # can be updated sequentially
        for group in groupedids:
            full_kperms.update(set(self.find_kperms(group)))

        if __debug__:
            pickle.dump(full_kperms,open("debugfull_kperms.pickle","wb"))

        add_kperms=[kpr for kpr in full_kperms if kpr.domain.intersection({0})]

        # for the first iteration,
        # we can keep only kpr if the 2 first oligos overlap kpr.perm[:2] or consist only of {0}
        add_kperms=[kpr for kpr in add_kperms
                    if data.OligoPeak.tail_overlap(kpr.perm[0].seq,kpr.perm[1].seq)
                    or len(kpr.domain)==1]
        #partitions=[[kpr] for kpr in add_kperms] # before
        partitions=[data.Partition(perms=[kpr],domain=kpr.domain) for kpr in add_kperms]

        for index in range(len(self.oligos)):
            print("len(partitions)=",len(partitions))
            print("index=",index)
            add_kperms=[kpr for kpr in full_kperms if kpr.span.intersection({index})]
            print("len(add_kperms)=",len(add_kperms))
            added_partitions=[] # type: List[data.Partition]
            for part in partitions:
                # extend the part until all indices<index are in domain
                # kpr in add_kperms which do not intersect with part
                new_parts=self.construct_scaffold(part,add_kperms,index+1) # test should be faster
                added_partitions+=new_parts

            #ranked=self.rank_by_noverlaps(added_partitions,self.ooverl,index)
            self.increment_noverlaps(added_partitions,self.ooverl,index+1)
            #max_overlap=max(i[0] for i in ranked) # before
            max_overlap=max(part.noverlaps for part in added_partitions) # pylint: disable=no-member
            partitions=[part for part in added_partitions if part.noverlaps==max_overlap] # pylint: disable=no-member
            if __debug__:
                pickle.dump(partitions,open("debugpartitions"+str(index)+".pickle","wb"))

            # HERE
            # TESTING! comment the following command
            #partitions=[part for part in added_partitions if part.noverlaps>max_overlap-3] # pylint: disable=no-member
            # can add a restriction on the stretch,bias

            # if 2 partitions differ locally (i.e. by a segment), save the segments
            # and recreate a partitions using the shared perms (domain inter) at index
            resume_parts=data.Partition.reduce_partitions(partitions,index)
            if __debug__:
                pickle.dump(resume_parts,open("debugresume_parts"+str(index)+".pickle","wb"))

            partitions=resume_parts # still testing
            # implement reconstruction method
            # write the method to list the final result (i.e. all possible partitions)
        return partitions

    def find_kperms(self,group:Tuple[int, ...])->Generator:
        u'''
        finds the permutations of oligos in cores
        and permutations from corrections (changed indices must be in both core_groups)
        '''
        idsperbatch=self.collection.idsperbatch
        batchfilter=processor.BetweenBatchFilter(idsperbatch=idsperbatch)
        ooverlfilter=processor.RequireOverlapFilter(oligos=self.oligos,
                                                    min_ooverl=self.ooverl)
        # compute all possible permutations # brute force
        kpermids=itertools.permutations(group) # generator
        firstfiltered = filter(ooverlfilter,kpermids) # type: ignore
        secondfiltered = filter(batchfilter,firstfiltered) # type: ignore
        for kprid in secondfiltered:
            for kpr in self.find_subkperms_from_permids(kprid):
                yield kpr

    def find_subkperms_from_permids(self,kpermids:Tuple[int, ...])->List[data.OligoKPerm]:
        u'''finds all sub kperms within a permids
        eg : (0,2,1,3,6,4,5) will return kperms conrresponding to [(0,),(1,2),(4,6,5)]
        '''
        cyclicsubs=self.find_cyclicsubs(kpermids)
        kperms=list(frozenset(self.cperm2kperm(self.oligos,sub) for sub in cyclicsubs))
        return kperms

    @staticmethod
    def cperm2kperm(oligos,cpermids:Tuple[int,...])->data.OligoKPerm:
        u'translates cyclic permutation to kperm'
        toprm={cpermids[k]:v for k,v in enumerate(cpermids[1:])}
        toprm.update({cpermids[-1]:cpermids[0]})
        kpermids=tuple(toprm[i] if i in toprm else i for i in range(min(cpermids),max(cpermids)+1))
        return data.OligoKPerm(oligos=oligos,
                               kperm=[oligos[i] for i in kpermids],
                               kpermids=numpy.array(kpermids),
                               domain=frozenset(cpermids))

    # ok but k-cycles are k duplicated
    @staticmethod
    def find_cyclicsubs(perm:Tuple[int, ...]):
        u'find sub-kpermutations within the permutation'
        # compute the new positions for each sub-kperm
        srtprm=sorted(perm)
        subkprms=[]
        for val in srtprm:
            kpr=[val]
            if perm[srtprm.index(val)]==kpr[0]:
                subkprms.append(tuple(kpr))
                continue
            kpr.append(perm[srtprm.index(val)])
            while kpr[-1]!=kpr[0]:
                kpr.append(perm[srtprm.index(kpr[-1])])

            subkprms.append(tuple(kpr[:-1]))

        return list(set(subkprms))

    # check if these methods could be useful here

    def find_groupperms(self,group:Tuple[int, ...])->Generator:
        u'''
        finds the permutations of oligos of a group
        and permutations from corrections (changed indices must be in both core_groups)
        '''
        idsperbatch=self.collection.idsperbatch
        batchfilter=processor.BetweenBatchFilter(idsperbatch=idsperbatch)
        ooverlfilter=processor.RequireOverlapFilter(oligos=self.oligos,
                                                    min_ooverl=self.ooverl)
        # compute all possible permutations # brute force
        kpermids=itertools.permutations(group) # generator
        firstfiltered = filter(ooverlfilter,kpermids) # type: ignore
        secondfiltered = filter(batchfilter,firstfiltered) # type: ignore
        for kprid in secondfiltered:
            yield data.OligoKPerm(oligos=self.oligos,
                                  kperm=[self.oligos[i] for i in kprid],
                                  kpermids=numpy.array(kprid))

    # needs better implementation
    # pylint: disable=no-self-use
    def fix_horizon(self,
                    partitions:List[List[data.OligoPerm]],
                    group:Tuple[int, ...])->List[List[data.OligoPerm]]:
        u'horizon is the ensemble of kperms which cannot modify by any subsequent combination'
        horizon=min(group) # set(group)
        for partid,part in enumerate(partitions):
            if len(part)==1:
                continue
            #to_fix=[(idx,kpr) for idx,kpr in enumerate(part)
            #        if not kpr.domain.intersection(horizon)]
            to_fix=[(idx,kpr) for idx,kpr in enumerate(part)
                    if all(i<horizon for i in  kpr.domain)]
            if len(to_fix)==0:
                continue
            merged=data.OligoPerm.add(*[fix[1] for fix in to_fix])
            fixed=[fix[0] for fix in to_fix]
            partitions[partid]=[merged]+[part[i] for i in range(len(part)) if not i in fixed]
        return partitions
