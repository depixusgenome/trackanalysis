#!/usr/bin/env python3
# -*- coding: utf-8 -*-

u'class for oligo assemby'
import pickle
import itertools
from typing import List, Tuple, Dict # pylint: disable=unused-import

from utils import initdefaults
import assemble.processor as processor
import assemble.scores as scores
import assemble.data as data
import assemble._utils as utils

# should define a Partition class as a container for List[data.OligoPerm]
# with fix_horizon(group), add2partitions as methods

# two things to change: the fix_horizon cdt on all(i <group for i in kperm.domain)
# keep noverlaps max -1 and -2 ?
# for code which needs improvements : see comments  # must be improved
class QOli:
    u'small class to combine to find kperms of OligoPeaks'
    def __init__(self,**kwa):
        self.idxs=kwa.get("idxs",[-1])
        self.seq=kwa.get("seq","")

    def __add__(self,other):
        return QOli(seq=self.seq+other.seq,idxs=self.idxs+other.idxs)

# need to call generators as often as possible
# find a better way to compute the kperms
# can add each additionnal kperm at a time and keep only those that are not already represented
# then compute rank  and discard the other ones
# do not reconsider kperms already tested with add_kperms
class PieceAssemble:
    u'''
    much faster version of assembler
    sequence is assembled sequentially starting from the first oligos
    adding iteratively groups of oligos which can permute
    call as :
    PieceAssemble(nscale=1,
                  collection=collection,
                  ooverl=3,
                  scoring=scores.ScoreAssembly(ooverl=3))
    '''
    nscale=1 # type: float
    collection=data.BCollection() # type: data.BCollection
    ooverl=1
    #scoring=scores.ScoreAssembly()
    @initdefaults(frozenset(locals()))
    def __init__(self,**kwa):
        pass

    @property
    def oligos(self):
        u'returns oligos'
        return self.collection.oligos

    def compute(self):
        u'''
        reorder the oligos piecewise
        '''
        # oligos should be ordered by pos (for a given stretch and bias)
        groupedids = utils.group_overlapping_normdists([oli.dist
                                                        for oli in self.oligos],nscale=1)[1]
        if __debug__:
            pickle.dump(groupedids,open("groupedids.pickle","wb"))

        # compute for the first group then correct as we had more to it
        all_kperms = self.find_kperms(groupedids[0])
        # reduce the number of kperms
        # keep the best

        partitions=[[kperm] for kperm in all_kperms]
        # need to add more structure, call method to reduce the number of partitions
        by_noverlaps=self.rank_byoverlaps(partitions)
        min_overlaps=sorted(set(i[0] for i in by_noverlaps),reverse=True)[0]
        bestooverl=[rkd for idx,rkd in enumerate(by_noverlaps) if rkd[0]>=min_overlaps]
        partitions=[rkd[1] for rkd in bestooverl]

        for groupid,group in enumerate(groupedids[1:]):
            if __debug__:
                print("groupid="+str(groupid)+" out of "+str(len(groupedids[1:])))
                pickle.dump(partitions,open("beforepartitions"+str(groupid)+".pickle","wb"))
            # check that fix_horizon works properly
            partitions=self.fix_horizon(partitions,group)
            if __debug__:
                pickle.dump(partitions,open("afterpartitions"+str(groupid)+".pickle","wb"))

            # should include a test to discard already test kperms using set().intersection()
            # can generate the kperms sequentially
            add_kperms=self.find_kperms(group)
            print("len(add_kperms)=",len(add_kperms))
            if len(add_kperms)==0:
                continue
            if __debug__:
                pickle.dump(add_kperms,open("add_kperms"+str(groupid)+".pickle","wb"))
            if __debug__:
                pickle.dump(all_kperms,open("all_kperms"+str(groupid)+".pickle","wb"))

            # for each kperm in add kperms look if they present a better match than previous ones

            # can add kperms in add_kperms sequentially and keep the best

            # compute the scores to each partitions
            partitions=self.add2partitions(partitions,[[kpr] for kpr in add_kperms])
            print("before reduce len(partitions)=",len(partitions))
            if __debug__:
                pickle.dump(partitions,open("addedpartitions"+str(groupid)+".pickle","wb"))

            partitions=self.reduce_partitions(partitions)
            print("before reduce len(partitions)=",len(partitions))
            # keep the ones with max noverlaps or
            # noverlaps such that 10% of the best according to noverlaps
            # discards the worst, keep the ones with max overlaps + the 10% best ones

            # faster to discard partitions with low noverlaps first
            by_noverlaps=self.rank_byoverlaps(partitions)
            if __debug__:
                print("consider keeping 10% best including pdfcost, from")
                print(len(by_noverlaps))
            # still too slow for large prec
            #min_overlaps=by_noverlaps[int(0.1*len(partitions))+1][0]
            print("set of noverlaps=",sorted(set(i[0] for i in by_noverlaps),reverse=True))
            # need to formalise the next line
            min_overlaps=sorted(set(i[0] for i in by_noverlaps),reverse=True)[0]

            bestooverl=[rkd for idx,rkd in enumerate(by_noverlaps) if rkd[0]>=min_overlaps]

            ranked_partitions=self.rank_partitions([i[1] for i in bestooverl])

            keepbest=list(ranked_partitions)

            partitions=[rkd[2] for rkd in keepbest]


        return partitions,[data.OligoPerm.add(*part) for part in partitions],ranked_partitions


    # tocheck
    #pylint: disable=no-self-use
    def oldreduce_partitions(self,
                             partitions:List[List[data.OligoPerm]])->List[List[data.OligoPerm]]:
        u'''
        if two partitions result in the same permids, keep the one with smallest domain
        '''
        # before
        merged=[data.OligoPerm.add(*part) for part in partitions]
        print("merged done")
        smerged=sorted([(tuple(val.permids),
                         tuple(sorted(val.domain)),
                         partitions[idx])
                        for idx,val in enumerate(merged)],
                       key=lambda x: x[0])
        print("smerged done")
        reduced=[]
        for grp in itertools.groupby(smerged,key=lambda x:x[0]):
            consider=list(grp[1])
            domains=set(i[1] for i in consider)
            tokeep=[]
            for dom in domains:
                if not any(set(i) < set(dom) for i in domains):
                    tokeep.append(dom)
            for tkp in tokeep:
                reduced.append([i[2] for i in consider if i[1]==tkp][0])
        return reduced

    def reduce_partitions(self,
                          partitions:List[List[data.OligoPerm]])->List[List[data.OligoPerm]]:
        u'reduce mem overload'
        all_merged=dict() # type: Dict[Tuple[int,...],List[data.OligoPerm]]
        for part in partitions:
            #print(idx)
            merged=data.OligoPerm.add(*part)
            try:
                cmp_with=all_merged[tuple(merged.permids)]
                dealt=False
                for oidx,opart in enumerate(cmp_with):
                    if opart[0]<=merged.domain:
                        # less constrained was already found
                        dealt=True
                        break
                    if opart[0]>merged.domain:
                        # replace with less constrained partition
                        all_merged[tuple(merged.permids)][oidx]=(merged,part)
                        dealt=True
                        break
                if not dealt:
                    all_merged[tuple(merged.permids)].append((merged.domain,part))
            except KeyError:
                all_merged[tuple(merged.permids)]=[(merged.domain,part)]
        return [mpart[1] for value in all_merged.values() for mpart in value]

    # needs testing
    def add2partitions(self,partitions1,partitions2):
        u'new (faster) implementation'
        addedpartitions=[]
        for part2 in partitions2:
            modified_dom=set()
            for kpr in part2:
                modified_dom.update(kpr.domain)
            for part1 in partitions1:
                tocombine=[kpr for kpr in part1 if kpr.domain.intersection(modified_dom)]
                tocombine+=part2
                fixed=[kpr for kpr in part1 if not kpr.domain.intersection(modified_dom)]
                combined=self.find_kpermpartitions(tocombine)
                for comb in combined:
                    addedpartitions.append(fixed+comb)
        return addedpartitions

    def rank_partitions(self,partitions):
        u'''
        computes the noverlaps for each partitions
        calculus is done over the whole sequence, TO FIX!
        '''
        merged_partitions = [data.OligoPerm.add(*kperms) for kperms in partitions]
        merged_kperms=[data.OligoKPerm(kperm=prm.perm) for prm in merged_partitions]
        scored=[]
        for kprmid,kprm in enumerate(merged_kperms):
            score= scores.ScoreAssembly(perm=kprm,
                                        ooverl=self.ooverl)
            scored.append((score.noverlaps(),score.density(),partitions[kprmid]))
        return sorted(scored,key=lambda x:(-x[0],x[1]))

    # merge with rank_partitions
    def rank_byoverlaps(self,partitions):
        u'''
        computes the noverlaps for each partitions
        calculus is done over the whole sequence, TO FIX!
        '''
        merged_partitions = [data.OligoPerm.add(*kperms) for kperms in partitions]
        merged_kperms=[data.OligoKPerm(kperm=prm.perm) for prm in merged_partitions]
        scored=[]
        for kprmid,kprm in enumerate(merged_kperms):
            score= scores.ScoreAssembly(perm=kprm,
                                        ooverl=self.ooverl)
            scored.append((score.noverlaps(),partitions[kprmid]))
        return sorted(scored,key=lambda x:-x[0])

    # must be improved
    def find_kperms(self,group:Tuple[int, ...])->List[data.OligoPerm]:
        u'''
        finds the permutations of oligos in cores
        and permutations from corrections (changed indices must be in both core_groups)
        '''
        idsperbatch=self.collection.idsperbatch
        batchfilter=processor.BetweenBatchFilter(idsperbatch=idsperbatch)
        ooverlfilter=processor.RequireOverlapFilter(oligos=self.oligos,
                                                    min_ooverl=self.ooverl)
        okperms=[]
        # compute all possible permutations # brute force
        permids=itertools.permutations(group) # generator
        firstfiltered = filter(ooverlfilter,permids) # type: ignore
        secondfiltered = filter(batchfilter,firstfiltered) # type: ignore
        for permid in secondfiltered:
            okperms.append(data.OligoKPerm(oligos=self.oligos,
                                           kperm=[self.oligos[i] for i in permid],
                                           kpermids=permid))

        return okperms

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

    def qkpermsfromqolis(self,qolis:List[QOli])->List[List[QOli]]:
        u'''
        recursive function
        pairs oligos 2 by 2 until none can be paired or all are paired
        '''
        # if qidx==rpair: continue
        if len(qolis)==1:
            return [qolis]
        qkperms=[] # type: List[List[QOli]]
        left=[oli.seq[:self.ooverl] for oli in qolis]
        right=[oli.seq[-self.ooverl:] for oli in qolis]
        for qidx,qoli in enumerate(qolis):
            rpairswith=[idx for idx,val in enumerate(right) if val==qoli.seq[:self.ooverl]
                        and idx!=qidx]
            for rpair in rpairswith:
                pair=qolis[rpair]+qoli
                qkperm=list(qolis)
                qkperm[rpair]=pair
                qkperm.pop(qidx)
                qkperms+=[qkperm]
            if len(rpairswith)>0:
                qkperms+=self.qkpermsfromqolis(qkperm)

            lpairswith=[idx for idx,val in enumerate(left) if val==qoli.seq[-self.ooverl:]
                        and idx!=qidx]
            for lpair in lpairswith:
                #print('lpairing',qoli.seq,qolis[lpair].seq)
                pair=qoli+qolis[lpair]
                qkperm=list(qolis)
                qkperm[lpair]=pair
                qkperm.pop(qidx)
                qkperms+=[qkperm]
            if len(lpairswith)>0:
                qkperms+=self.qkpermsfromqolis(qkperm)
        return qkperms

    # ooverl will eventually be be the minimal number of overlapping
    def test_find_kperms(self,
                         group:Tuple[int, ...])->List[data.OligoKPerm]:
        u'''
        trying to find alternative way to compute possible permutations of oligos
        (which is long and very inefficient for prec>5nm
        call as find_kperms([oligos[i] for i in core])
        will still need to filter out permutations of oligos amongst the same batch
        '''

        qolis=[QOli(seq=self.oligos[i].seq,idxs=[i]) for i in group]
        qkperms=self.qkpermsfromqolis(qolis)
        kperms=[]
        for qkprm in qkperms:
            kpr=[] # type: List[int]
            for qoli in qkprm:
                kpr+=qoli.idxs
            kperms.append(kpr)

        idsperbatch=self.collection.idsperbatch
        batchfilter=processor.BetweenBatchFilter(idsperbatch=idsperbatch)

        return list(filter(batchfilter,kperms))

    def find_kpermpartitions(self,kperms):
        u'''
        finds the kperms which can be combined
        '''
        parts=[]
        seeds=[kpr for kpr in kperms if kpr.domain==set()]
        if seeds==[]:
            seeds=[kperms[0]]+[kpr for kpr in kperms[1:]
                               if kpr.domain.intersection(kperms[0].domain)]
        #print("seeds=",seeds)
        for seed in seeds:
            no_inter=[kpr for kpr in kperms
                      if not kpr in seeds
                      and not kpr.domain.intersection(seed.domain)]
            parts.extend(self.partition_from_seed(seed,no_inter))
        return parts

    def partition_from_seed(self,
                            seed:data.OligoKPerm,
                            kperms:List[scores.ScoredPermCollection])\
                            ->List[List[scores.ScoredPermCollection]]:
        u'''
        seed should not be in kperms nor any collection which intersects with seed
        recursive call
        '''
        if len(kperms)==0:
            return [[seed]]
        # look at each collection and see if they overlap with others
        intersections = list([i for i,v in enumerate(kperms)
                              if kpr.domain.intersection(v.domain)] for kpr in kperms)
        intersections = sorted(intersections,key=len,reverse=True)
        # if they only overlap with themselves, then they can all be merged
        if len(intersections[0])==1:
            return [[seed]+kperms]

        return [[seed]+toadd
                for i in intersections[0]
                for toadd in\
                self.partition_from_seed(kperms[i],
                                         [kpr for kpr
                                          in kperms
                                          if not kpr.domain.intersection(kperms[i].domain)])]
