#!/usr/bin/env python3
# -*- coding: utf-8 -*-

u'class for oligo assemby'
import pickle
import itertools
from typing import List, Tuple, Dict, Generator # pylint: disable=unused-import

import numpy
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
# -> need to discard kperms which are already computed
# (if no part contains latest max(group) then this partition has already been computed)
# then compute rank  and discard the other ones
class PieceAssemble: # pylint:disable=too-many-public-methods
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
    noverl_tol=0 # keep only the best partitions noverlaps wise
    #scoring=scores.ScoreAssembly()
    @initdefaults(frozenset(locals()))
    def __init__(self,**kwa):
        pass

    @property
    def oligos(self):
        u'returns oligos'
        return self.collection.oligos

    def compute(self): # pylint: disable=too-many-locals
        u'''
        reorder the oligos piecewise
        '''
        # oligos should be ordered by pos (for a given stretch and bias)
        groupedids = utils.group_overlapping_normdists([oli.dist
                                                        for oli in self.oligos],nscale=1)[1]
        if __debug__:
            pickle.dump(groupedids,open("groupedids.pickle","wb"))

        # compute for the first group then correct as we had more to it
        # instead of kperms take the list(set(subkperms))
        all_kperms = list(set(self.find_groupperms(groupedids[0])))
        # can't use find_kperms because we need sub permutation
        #all_kperms = list(set(self.find_kperms(groupedids[0])))
        # reduce the number of kperms
        # keep the best

        partitions=[[kpr] for kpr in all_kperms]
        print("computing first partition, done")
        # need to add more structure, call method to reduce the number of partitions
        by_noverlaps=self.rank_byoverlaps(partitions)
        min_overlaps=sorted(set(i[0] for i in by_noverlaps),reverse=True)[self.noverl_tol]
        bestooverl=[rkd for idx,rkd in enumerate(by_noverlaps) if rkd[0]>=min_overlaps]
        partskept=[rkd[1] for rkd in bestooverl] # must subdivide into subkperms
        #partitions=[rkd[1] for rkd in bestooverl]

        partitions=[]
        for part in partskept:
            adding=[]
            for kpr in part:
                adding+=[self.cperm2kperm(self.oligos,i)
                         for i in self.find_cyclicsubs(kpr.kpermids)]
                #adding+=self.find_subkperms_from_permids(kpr.kpermids)
            partitions.append(list(set(adding)))

        print("done")
        #prev_kperms=frozenset(list(set(self.find_kperms(groupedids[0]))))
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
            #add_kperms=self.find_min_kperms(group)
            add_kperms=list(set(self.find_kperms(group)))
            #add_kperms=list(set(self.find_groupperms(group)))

            print("len(add_kperms)=",len(add_kperms))
            if len(add_kperms)==0:
                continue
            if __debug__:
                pickle.dump(add_kperms,open("add_kperms"+str(groupid)+".pickle","wb"))
            if __debug__:
                pickle.dump(all_kperms,open("all_kperms"+str(groupid)+".pickle","wb"))

            # for each kperm in add kperms look if they present a better match than previous ones

            # compute the scores to each partitions
            # only considering kperms which have not been considered previously
            # to_add=list(frozenset(add_kperms)-frozenset(prev_kperms)) # before
            # partitions=self.add2partitions(partitions,[[kpr] for kpr in add_kperms]) # before

            partitions=self.add2partitions(partitions,[[kpr] for kpr in add_kperms])
            #prev_kperms=frozenset(add_kperms)

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
            min_overlaps=sorted(frozenset(i[0] for i in by_noverlaps),reverse=True)[self.noverl_tol]

            bestooverl=[rkd for idx,rkd in enumerate(by_noverlaps) if rkd[0]>=min_overlaps]

            ranked_partitions=self.rank_partitions([i[1] for i in bestooverl])

            keepbest=list(ranked_partitions)

            partitions=[rkd[2] for rkd in keepbest]


        return partitions,[data.OligoPerm.add(*part) for part in partitions],ranked_partitions

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
                combined=self.find_kpermpartitions(list(frozenset(tocombine)))
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

    # WRONG!
    def find_min_orders(self,group:Tuple[int, ...])->List[data.OligoKPerm]:
        u'''
        computes the segments of permuted elements of the group
        such that elements in the segment overlap
        '''
        grpkperms=self.find_groupperms(group)
        subkperms=[] # type: List[data.OligoKPerm]
        for gprm in grpkperms:
            subkperms+=self.kperm2minkperms(self.oligos,self.ooverl,gprm)

        return list(frozenset(subkperms))

    @staticmethod
    def kperm2minkperms(oligos:List[data.OligoPeak],
                        ooverl:int,
                        kperm:data.OligoKPerm)->List[data.OligoKPerm]:
        u'''input: oligos, a kperm
        the kperm was computed from the find_groupperms
        uses oligo sequences to find the sub-permutation
        could use arrays
        itertools
        '''
        if len(kperm.kpermids)<2:
            return kperm

        marker=0
        cluster=[]
        for idx,val in enumerate(kperm.kpermids[:-1]):
            cluster.append((marker,val))
            # if not contiguous change marker
            if oligos[val].seq[-ooverl:]!=oligos[kperm.kpermids[idx+1]].seq[:ooverl]:
                marker+=1

        cluster.append((marker,kperm.kpermids[-1]))
        subs=[]
        for grp in itertools.groupby(cluster,key=lambda x:x[0]):
            subids=tuple(i[1] for i in grp[1])
            subs.append(data.OligoKPerm(oligos=oligos,
                                        kperm=[oligos[i] for i in subids],
                                        kpermids=numpy.array(subids),
                                        domain=frozenset(subids))) # to check
        return subs

    def find_subkperms_from_permids(self,kpermids:Tuple[int, ...])->List[data.OligoKPerm]:
        u'''finds all sub kperms within a permids
        eg : (0,2,1,3,6,4,5) will return kperms conrresponding to [(0,),(1,2),(4,6,5)]
        '''
        cyclicsubs=self.find_cyclicsubs(kpermids)
        kperms=list(frozenset(self.cperm2kperm(self.oligos,sub) for sub in cyclicsubs))
        return kperms

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
            if len(lpairswith)>0 or len(rpairswith)>0:
                qkperms+=self.qkpermsfromqolis(qkperm)

        return qkperms

    # ooverl will eventually be be the minimal number of overlapping
    def test_find_kperms(self,
                         group:Tuple[int, ...]):
        u'''
        trying to find alternative way to compute possible permutations of oligos
        (which is long and very inefficient for prec>5nm
        call as find_kperms([oligos[i] for i in core])
        will still need to filter out permutations of oligos amongst the same batch
        use addpartitions but this time permutations may not be independent
        find all 2-permutations
        take possible combinations of 2 permutations
        filter out
        qkperms=self.qkpermsfromqolis(qolis)
        kperms=[]
        for qkprm in qkperms:
            kpr=[] # type: List[int]
            for qoli in qkprm:
                kpr+=qoli.idxs
            kperms.append(kpr)

        # if qidx==rpair: continue
        if len(qolis)==1:
            return [qolis]
        qkperms=[] # type: List[List[QOli]]
        for qidx,qoli in enumerate(qolis):
            rpairswith=[idx for idx,val in enumerate(right) if val==qoli.seq[:self.ooverl]
                        and idx!=qidx]
            for rpair in rpairswith:
                pair=qolis[rpair]+qoli
                qkperm=list(qolis)
                qkperm[rpair]=pair
                qkperm.pop(qidx)
                qkperms+=[qkperm]
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
            if len(lpairswith)>0 or len(rpairswith)>0:
                qkperms+=self.qkpermsfromqolis(qkperm)
        idsperbatch=self.collection.idsperbatch
        batchfilter=processor.BetweenBatchFilter(idsperbatch=idsperbatch)


        '''
        # probably won't work

        qolis=tuple(QOli(seq=self.oligos[i].seq,idxs=[i]) for i in group)
        left=tuple(oli.seq[:self.ooverl] for oli in qolis)
        right=tuple(oli.seq[-self.ooverl:] for oli in qolis)

        # convert this into permutations
        permsof2=[]
        for qidx,qoli in enumerate(qolis):
            base=group[:qidx]+group[qidx+1:]
            for idx,val in enumerate(right):
                if val==qoli.seq[:self.ooverl]:
                    if idx<qidx:
                        print("idx=",idx)
                        print("qidx=",qidx)
                        print("right=",base[:idx]+(qidx,)+base[idx:])
                        permsof2.append(base[:idx-1]+(qidx,)+base[idx-1:])
                    else:
                        print("idx=",idx)
                        print("qidx=",qidx)
                        print("right=",base[:idx+1]+(qidx,)+base[idx+1:])
                        permsof2.append(base[:idx]+(qidx,)+base[idx:])


            for idx,val in enumerate(left):
                if val==qoli.seq[-self.ooverl:]:
                    if idx<qidx:
                        print("idx=",idx)
                        print("qidx=",qidx)
                        print("left=",base[:idx-1]+(qidx,)+base[idx-1:])
                        permsof2.append(base[:idx-1]+(qidx,)+base[idx-1:])
                    else:
                        print("idx=",idx)
                        print("qidx=",qidx)
                        print("left=",base[:idx]+(qidx,)+base[idx:])
                        permsof2.append(base[:idx]+(qidx,)+base[idx:])

        # apply filter on the 2-perms
        print(len(permsof2))

        # take 2**len(permsof2)

        return permsof2#list(filter(batchfilter,kperms))


    def find_kpermpartitions(self,kperms:List[data.OligoKPerm]):
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
