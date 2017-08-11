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
import pickle # pylint: disable=unused-import
import numpy
import networkx
from . import data
from . import scores
from . import processor
from . import _utils as utils

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

class PermGenerator:
    '''
    generates eligible permutation
    will need to filter out on permutations within batch
    A couple things to check:
    * the kperms are not the same but the ones in here seems more correct
    due in part to the fact that shift  was not  set to 1 in tail_overlaps
    leading to additional but unecessary kperms
    * need to check whether we still need sub (cyclic) permutations. Probably not.
    * need to generate single kperm [1],[2],[3] for (1,2,3)
    '''

    def __init__(self,**kwa):
        'creates the full graph from oligos'
        self.ooverl=kwa.get("ooverl",-1)
        self.graph=networkx.DiGraph()
        self.__oligos=kwa.get("oligos",[]) # type: List[data.Oligo]
        self.__gengraph()

    @property
    def oligos(self):
        'oligos'
        return self.__oligos

    @oligos.setter
    def oligos(self,values):
        'setter'
        self.__oligos=values
        self.graph.clear()
        self.__gengraph()

    def __gengraph(self)->None:
        'creates the graph corresponding to the sorted group of oligos'
        tail=data.Oligo.tail_overlap
        edges=[(idx,idx+1) for idx in range(len(self.oligos))]
        if self.ooverl>0:
            for idx1,idx2 in itertools.permutations(range(len(self.oligos)),2):
                if len(tail(self.oligos[idx1].seq,self.oligos[idx2].seq,shift=1))==self.ooverl:
                    edges+=[(idx1,idx2)]

        self.graph.add_edges_from(frozenset(edges))

    def find_kpermids(self,group:Tuple[int, ...])->Generator:
        'find eligible permutation within the subgraph group'
        subgraph=self.graph.subgraph(group)
        for oli1,oli2 in itertools.permutations(subgraph.nodes(),2):
            for perm in networkx.all_simple_paths(subgraph,source=oli1,target=oli2):
                yield tuple(perm)

    def find_kperms(self,group:Tuple[int, ...])->Generator:
        'generates '
        for prmid in self.find_kpermids(group):
            yield data.OligoKPerm(oligos=self.oligos,
                                  kperm=[self.oligos[i] for i in prmid],
                                  kpermids=numpy.array(prmid))

class Shuffler:
    'align oligo by maximising the overlap one index at a time'
    def __init__(self,**kwa):

        oligos=kwa.get("oligos",[]) # type: data.OligoPeak
        #self.collection=kwa.get("collection",data.BCollection()) # type:data.BCollection
        self.ooverl=kwa.get("ooverl",-1) # type: int
        self.nscale=kwa.get("nscale",1) # type: int
        self.permgen=PermGenerator(ooverl=self.ooverl)

        if oligos:
            self.collection=data.BCollection.from_oligos(oligos)
            self.permgen.oligos=self.collection.oligos


    @property
    def oligos(self):
        '(ordered) oligos from self.collection'
        return self.collection.oligos

    @oligos.setter
    def oligos(self,values):
        self.collection=data.BCollection.from_oligos(values)
        self.permgen.oligos=self.collection.oligos

    # to pytest
    @staticmethod
    def increment_noverlaps(partitions:List[data.Partition],
                            ooverl:int,
                            index:int):
        'increments the noverlaps value up to index'
        for partid,part in enumerate(partitions):
            # should be ok but needs checking
            merged=part.merge() # careful, merge merges only common perms in case of ambiguities
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

    # still long
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
        # if __debug__:
        #     pickle.dump(self.oligos,open("debugoligos.pickle","wb"))

        print("looking for permutations")
        groupedids=utils.group_overlapping_normdists([oli.dist for oli in self.oligos],
                                                     nscale=self.nscale)[1]
        print(f"len(groupedids)={len(groupedids)}")
        # if __debug__:
        #     pickle.dump(groupedids,open("debuggroupedids.pickle","wb"))

        full_kperms=set([]) # can be updated sequentially
        for group in groupedids:
            full_kperms.update(set(self.find_kperms(group)))

        print(f"len(full_kperms)={len(full_kperms)}")
        # if __debug__:
        #     pickle.dump(full_kperms,open("debugfull_kperms.pickle","wb"))

        add_kperms=[kpr for kpr in full_kperms if kpr.domain.intersection({0})]

        # for the first iteration,
        # we can keep only kpr if the 2 first oligos overlap kpr.perm[:2] or consist only of {0}
        add_kperms=[kpr for kpr in add_kperms
                    if data.OligoPeak.tail_overlap(kpr.perm[0].seq,kpr.perm[1].seq)
                    or len(kpr.domain)==1]

        print(f"len(add_kperms)={len(add_kperms)}")
        #partitions=[[kpr] for kpr in add_kperms] # before
        partitions=[data.Partition(perms=[kpr],domain=kpr.domain) for kpr in add_kperms]

        for index in range(len(self.oligos)):
            print(f"index={index}")
            add_kperms=[kpr for kpr in full_kperms if kpr.span.intersection({index})]
            added_partitions=[] # type: List[data.Partition]

            for part in partitions:
                # extend the part until all indices<index are in domain
                # kpr in add_kperms which do not intersect with part
                new_parts=self.construct_scaffold(part,add_kperms,index+1)
                added_partitions+=new_parts

            self.increment_noverlaps(added_partitions,self.ooverl,index+1)
            max_overlap=max(part.noverlaps for part in added_partitions) # pylint: disable=no-member
            partitions=[part for part in added_partitions if part.noverlaps==max_overlap] # pylint: disable=no-member
            # if __debug__:
            #     for testid,testpart in enumerate(partitions):
            #         print(f"testid={testid}")
            #         testmerged=data.OligoPerm.add(*testpart.perms) # pylint: disable=unused-variable
            #         print("ok")

            if __debug__:
                pickle.dump(partitions,open(f"parts_index{index}.pickle","wb"))
            resume_parts=data.Partition.reduce_partitions(partitions,index)
            partitions=resume_parts

        return partitions


    def run(self,**kwa):
        '''
        runs the base_per_base algorithm
        scores partitions
        and return the result (score+tuple of oligos)
        '''
        self.collection=data.BCollection.from_oligos(kwa.get("oligos",[]))
        partitions=self.base_per_base()

        # score each partition
        return partitions

    # method to test!
    def find_kperms(self,group:Tuple[int, ...])->Generator:
        '''
        generates eligible permutations using networkx
        '''
        for kprid in self.permgen.find_kpermids(group):
            for kpr in self.find_subkperms_from_permids(kprid):
                yield kpr

    # works but slow
    def old_find_kperms(self,group:Tuple[int, ...])->Generator:
        '''
        finds the permutations of oligos in cores
        and permutations from corrections (changed indices must be in both core_groups)
        '''
        idsperbatch=self.collection.idsperbatch
        batchfilter=processor.BetweenBatchFilter(idsperbatch=idsperbatch)
        ooverlfilter=processor.RequireOverlapFilter(oligos=self.oligos,
                                                    min_ooverl=self.ooverl)
        # compute all possible permutations # brute force
        # TO FIX: quick fix would use itertools.product
        # to generate possible permutations between groups
        kpermids=itertools.permutations(group) # generator
        firstfiltered = filter(ooverlfilter,kpermids) # type: ignore
        secondfiltered = filter(batchfilter,firstfiltered) # type: ignore
        for kprid in secondfiltered:
            for kpr in self.find_subkperms_from_permids(kprid):
                yield kpr

    def find_subkperms_from_permids(self,kpermids:Tuple[int, ...])->List[data.OligoKPerm]:
        '''finds all sub kperms within a permids
        eg : (0,2,1,3,6,4,5) will return kperms conrresponding to [(0,),(1,2),(4,6,5)]
        '''
        cyclicsubs=self.find_cyclicsubs(kpermids)
        kperms=list(frozenset(self.cperm2kperm(self.oligos,sub) for sub in cyclicsubs))
        return kperms

    @staticmethod
    def cperm2kperm(oligos,cpermids:Tuple[int,...])->data.OligoKPerm:
        'translates cyclic permutation to kperm'
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
        'find sub-kpermutations within the permutation'
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
