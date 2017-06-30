#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''
permutes oligos to find maximal overlapping
checks base per base that the constructed sequence is optimal
allows for multiple possibilities
can be optimised
'''

import itertools
from typing import Tuple, List, Generator, Dict # pylint: disable=unused-import
import pickle
import numpy
import assemble.data as data
import assemble.scores as scores
import assemble.processor as processor
import assemble._utils as utils

# can select a sub set of the full_kperms to construct the scaffolding
# can only check the overlap on the previous oligo in rank_by_noverlaps
# can merge partitions right after ranking so that we don't merge the first kperms each time
class BaseWise:
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
    def rank_by_noverlaps(partitions:List[List[data.OligoKPerm]],ooverl,index:int):
        '''
        to check that the score is computed on the correct index
        if we construct partitions index per index discarding those that are not optimal
        we can limit to checking that the perm[index-1:index] do overlap
        '''
        scored=[]
        for part in partitions:
            merged=data.OligoPerm.add(*part)
            if __debug__:
                if not all(i in merged.domain for i in range(index)):
                    print("missing index values in "+str(merged.domain))
                    print("index=",index)
                    raise ValueError

            kprm=data.OligoKPerm(kperm=merged.perm[:index])

            score= scores.ScoreAssembly(perm=kprm,
                                        ooverl=ooverl)
            scored.append((score.noverlaps(),part))

        return sorted(scored,key=lambda x:x[0],reverse=True)

    @classmethod
    def construct_scaffold(cls,
                           base:List[data.OligoPerm],
                           add_kperms:List[data.OligoKPerm],
                           index:int)->List[List[data.OligoKPerm]]:
        u'''
        the base is the starting partition is expand up to index.
        ie until domain for merged base
        does not produce duplicates
        '''
        merged=data.OligoPerm.add(*base)
        if all(i in merged.domain for i in range(index)):
            return [base]

        next_id=min([idx for idx in range(index) if not idx in merged.domain])
        to_return=[] # type: List[List[data.OligoKPerm]]
        to_add=[kprm for kprm in add_kperms if not merged.domain.intersection(kprm.domain)
                and next_id in kprm.domain]
        for kprm in to_add:
            to_return+=cls.construct_scaffold(base+[kprm],add_kperms,index)

        return to_return


    def base_per_base(self):
        'constructs the sequence with maximal overlapping one base at a time'
        groupedids=utils.group_overlapping_normdists([oli.dist for oli in self.oligos],
                                                     nscale=self.nscale)[1]
        full_kperms=set([]) # can be updated sequentially
        for group in groupedids:
            full_kperms.update(set(self.find_kperms(group)))

        if __debug__:
            pickle.dump(full_kperms,open("full_kperms.pickle","wb"))

        add_kperms=[kpr for kpr in full_kperms if kpr.domain.intersection({0})]

        # for the first iteration,
        # we can keep only kpr if the 2 first oligos overlap kpr.perm[:2] or consist only of {0}
        add_kperms=[kpr for kpr in add_kperms
                    if data.OligoPeak.tail_overlap(kpr.perm[0].seq,kpr.perm[1].seq)
                    or len(kpr.domain)==1]
        partitions=[[kpr] for kpr in add_kperms]

        for index in range(1,len(self.oligos)):
            print("len(partitions)=",len(partitions))
            print("index=",index)
            add_kperms=[kpr for kpr in full_kperms if frozenset(kpr.permids).intersection({index})]
            print("len(add_kperms)=",len(add_kperms))
            added_partitions=[]
            for part in partitions:
                # extend the part until all indices<index are in domain
                # kpr in add_kperms which do not intersect with part
                new_parts=self.construct_scaffold(part,full_kperms,index)
                added_partitions+=new_parts

            print(len(added_partitions))
            ranked=self.rank_by_noverlaps(added_partitions,self.ooverl,index)
            max_overlap=max(i[0] for i in ranked)
            # compute the noverlaps of data.OligoPerm.add(*part).perm between 0 and i<index
            # keep only the partitions which have maximal noverlaps
            # too restrictive?
            #partitions=pwassemble.add2partitions(partitions,[[kpr] for kpr in add_kperms])
            partitions=[part for score,part in ranked if score==max_overlap]
            if __debug__:
                pickle.dump(partitions,open("partitions"+str(index)+".pickle","wb"))
                pickle.dump(ranked,open("ranked"+str(index)+".pickle","wb"))
        # for each base from 0 to len(oligos)-1
        # select all kperms which intersect this base
        # keep all partitions
        # we can discard a partition iff:
        # we know that no permutation will never affect oligos before i
        # and that the (merged) partitition up to i-1 has lower noverlaps
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
    @staticmethod
    def reduce_partitions(partitions:List[List[data.OligoPerm]])->List[List[data.OligoPerm]]:
        u'''
        if two partitions result in the same permids, keep the one with smallest domain
        could test using set(object with hash from permids, domain and __eq__ if domain is the same)
        before keeping partitions with smaller domains
        '''
        all_merged=dict() # type: Dict[int,List[data.OligoPerm]]
        for part in partitions:
            merged=data.OligoPerm.add(*part)
            hashid=hash(merged.permids.tobytes())
            try:
                cmp_with=all_merged[hashid]
                dealt=False
                for oidx,opart in enumerate(cmp_with):
                    if opart[0]<=merged.domain:
                        # less constrained was already found
                        dealt=True
                        break
                    if opart[0]>merged.domain:
                        # replace with less constrained partition
                        all_merged[hashid][oidx]=(merged.domain,part)
                        dealt=True
                        break
                if not dealt:
                    all_merged[hashid]+=[(merged.domain,part)]
            except KeyError:
                all_merged[hashid]=[(merged.domain,part)]
        toout=[mpart[1] for value in all_merged.values() for mpart in value]
        all_merged.clear()
        del all_merged
        return toout


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
