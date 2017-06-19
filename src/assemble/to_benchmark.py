import pickle
import itertools
import re
from typing import List, Tuple
import numpy

from utils import initdefaults
import assemble.processor as processor
import assemble.scores as scores
import assemble.data as data
import assemble._utils as utils

#  for code which needs improvements : see comments  # must be improved


# to finish
class PiecewiseAssemble:
    u'''
    much faster version of assembler
    sequence is assembled sequentially starting from the first oligos
    adding iteratively groups of oligos which can permute
    call as :
    PiecewiseAssemble(nscale=1,
                      collection=collection,
                      ooverl=3,
                      scoring=scores.ScoreAssembly(ooverl=3))
    '''
    nscale=1 # type: float
    collection=data.BCollection() # type: data.BCollection
    ooverl=1
    scoring=scores.ScoreAssembly()
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
        groupedids = utils.group_overlapping_normdists([oli.dist for oli in self.oligos],nscale=1)[1]
        if __debug__:
            pickle.dump(groupedids,open("groupedids.pickle","wb"))
        all_kperms = [] # kperms which reconstruct the sequence
        # compute for the first group then correct as we had more to it
        all_kperms = self.find_kperms(groupedids[0])

        #partitions = []
        partitions=[[kperm] for kperm in all_kperms]
        for groupid,group in enumerate(groupedids[1:]):
            add_kperms=[i for i in self.find_kperms(group) if i.domain-set(groupedids[groupid])]
            print("len(add_kperms)=",len(add_kperms))
            if len(add_kperms)==0:
                continue
            if __debug__:
                pickle.dump(add_kperms,open("add_kperms"+str(groupid)+".pickle","wb"))
            if __debug__:
                pickle.dump(all_kperms,open("all_kperms"+str(groupid)+".pickle","wb"))

            # for each kperm in add kperms look if they present a better match than previous ones
            # filter out the others
            # can be optimized but basically compute the partitions

            # compute the scores to each partitions
            # this partitions also kperms which are from the same group (useless, generates duplicates) # TO FIX!
            #partitions=self.find_kpermpartitions(all_kperms+add_kperms)
            print("starting add2partitions")
            partitions=self.add2partitions(partitions,[[kpr] for kpr in add_kperms])
            if __debug__:
                pickle.dump(partitions,open("partitions.pickle","wb"))
            print("ended add2partitions")
            print("len(partitions)=",len(partitions))
            ranked_partitions=self.rank_partitions(partitions)

            # discards the worst, keep the ones with max overlaps + the 10% best ones 
            max_overlaps=max([rkpart[0] for rkpart in ranked_partitions])
            
            keepbest=[rkd for idx,rkd in enumerate(ranked_partitions) if rkd[0]==max_overlaps or idx<0.15*len(partitions)]

            partitions=[rkd[2] for rkd in keepbest]
            # if assembling of the partition is greater than the horizon we can merge kperms which are in the same patitions beyond the horizon!
            # as soon as some kperms
            # add the kpermutations
            all_kperms+=add_kperms

            # rank combined kperms

        #partitions=self.find_kpermpartitions(all_kperms)
        return partitions,[data.OligoPerm.add(*part) for part in partitions]

    # must be improved
    def add2partitions(self,
                       partitions1:List[List[data.OligoKPerm]],
                       partitions2:List[List[data.OligoKPerm]])->List[List[data.OligoKPerm]]:
        u'''
        adds 2 partitions together
        can combine any partition in part1 with any in part2
        but cannot combine kperms belonging to the same partition

        # before, wrong
        result=[]
        for part1 in partitions1:
            kperms1=[kpr for kpr in part1 if kpr.domain]
            set1=set()
            for kpr in kperms1:
                set1.update(kpr.domain)
            for part2 in partitions2:
                kperms2=[kpr for kpr in part2 if kpr.domain]
                set2=set()
                for kpr in kperms2:
                    set2.update(kpr.domain)
                # if all independant, add to result
                if not set1.intersection(set2):
                    result.append(part1+part2)

        # then tried...
        # to add a kperm to an existing partition
        # check if the kperm intersects with any kperm in partition
        # if no, append the kperm to the partition
        # else, collect intersecting kperms find partitions of collected kperms
        # and replace into the partitions
        combined=[]
        for part1 in partitions1:
            print("part1")
            #kperms1=[kpr for kpr in part1 if kpr.domain]
            for part2 in partitions2:
                print("part2")
                topartition=[]
                rmkpr1=[]
                # add to partition if intersect or domain==set()
                for kpr1,kpr2 in itertools.product(part1,part2):
                    if kpr1.domain.intersection(kpr2.domain):
                        topartition.extend([kpr1,kpr2])
                        rmkpr1.append(kpr1)
                print("len(topartition)=",len(topartition))
                for kpr1 in part1:
                    print(kpr1.kpermids)
                for kpr2 in part2:
                    print(kpr2.kpermids)
                if len(topartition)>0:
                    core=[kpr for kpr in part1 if not kpr in rmkpr1]
                    print("len(core)=",len(core))
                    patches=self.find_kpermpartitions(list(set(topartition)))
                    combined.extend([core+patch for patch in patches])
                else:
                    combined.extend([part1+part2])
        return combined
        '''
        # can be modified to reduce calculations
        # works but slow
        kperms1=set()
        for part1 in partitions1:
            kperms1.update(part1)
        kperms2=set()
        for part2 in partitions2:
            kperms2.update(part2)
        if __debug__:
            pickle.dump(kperms1,open("kperms1.pickle","wb"))
            pickle.dump(kperms2,open("kperms2.pickle","wb"))
        return self.find_kpermpartitions(list(kperms1)+list(kperms2))

    def rank_partitions(self,partitions):
        u'''
        computes the pdfcost and the noverlaps for each partitions
        calculus is done over the whole sequence, TO FIX!
        '''
        merged_partitions = [data.OligoPerm.add(*kperms) for kperms in partitions]
        merged_kperms=[data.OligoKPerm(kperm=prm.perm) for prm in merged_partitions]
        scored=[]
        for kprmid,kprm in enumerate(merged_kperms):
            score= self.scoring(kprm)
            scored.append((score.noverlaps,score.pdfcost,partitions[kprmid]))
        return sorted(scored,key=lambda x:(-x[0],x[1]))

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

    # ooverl will eventually be be the minimal number of overlapping 
    def test_find_kperms(self,oligos:List[data.OligoPeak],
                         ooverl=1,
                         fixed=None)->List[data.OligoKPerm]:
        u'''
        trying to find alternative way to compute possible permutations of oligos
        (which is long and very inefficient for prec>5nm 
        call as find_kperms([oligos[i] for i in core])
        will still need to filter out permutations of oligos amongst the same batch 
        '''
        if fixed is None:
            fixed=[]
        if len(fixed)==len(oligos):
            return []
        
        left=[oli.seq[:ooverl] for oli in oligos]
        right=[oli.seq[-ooverl:] for oli in oligos]
        kperms=[]
        for oliid,oligo in enumerate(oligos):
            if oligo in fixed:
                continue
            torightof=[idx+oliid+1 for idx,val in enumerate(left[oliid+1:]) if val==oligo.seq[-ooverl:]]
            toleftof=[idx+1+oliid+1 for idx,val in enumerate(right[oliid+1:]) if val==oligo.seq[ooverl:]]
            kperms+=[[oligos[:oliid]+oligos[oliid+1:]]]
        return kperms
    
    def find_kpermpartitions(self,kperms):
        u'''
        finds the kperms which can be combined
        '''
        parts=[]
        seeds=[kpr for kpr in kperms if kpr.domain==set()]
        if seeds==[]:
            seeds=[kperms[0]]+[kpr for kpr in kperms[1:] if kpr.domain.intersection(kperms[0].domain)]
        print("seeds=",seeds)
        for seed in seeds:
            parts.extend(self.partition_from_seed(seed,
                                                  [kpr for kpr in kperms
                                                   if not kpr in seeds]))
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
                for toadd in self.partition_from_seed(kperms[i],
                                                      [kpr for kpr
                                                       in kperms
                                                       if not kpr.domain.intersection(kperms[i].domain)])]

    
def operms(oligos,ooverl):
    u'''
    assume all oligos may permute
    should not return the neutral permutation
    '''
    end_seqs=[oli.seq[-ooverl:] for oli in oligos]
    start_seqs=[oli.seq[:ooverl] for oli in oligos]
    # use finditer
    [i.start() for i in re.finditer()]

    

def obsolete_analyse(division):
    merged=[scores.ScoredPermCollection.product(*i) for i in division[0]]
    oligohits=sorted(merged[0].scperms[0].perm.oligos,key=lambda x: x.pos0) # must be sorted by pos0
    correct_perms=[val for m in merged for idx,val in enumerate(m.scperms) if val.perm.perm==oligohits]
    print("len(correct_perms)=",len(correct_perms))
    noverlaps=[scores.ScoreAssembly(perm=scperm.perm,ooverl=3).noverlaps(attr="perm") for m in merged for scperm in m.scperms]
    print("len(noverlaps)=",len(noverlaps))
    pdfcosts=[scores.OptiKPerm(kperm=scperm.perm.perm).cost() for m in merged for scperm in m.scperms] 
    return pdfcosts,noverlaps,correct_perms

def analyse(scperms,oligos):
    # compute the pdfcost for each of the scperms
    # if only oligos which are not indexed in the domain are to add to the pdfcost
    print("computing pdfcost")
    scales=[i.dist.std() for i in oligos]
    assert all(scales[0]==i for i in scales[1:])
    factor=1/numpy.sqrt(2*numpy.pi*oligos[0].dist.std())
    
    pdfcosts=[i.pdfcost*(len(oligos)-len(i.domain))*factor for i in scperms]
    # compute the noverlaps for each
    print("computing noverlaps")
    noverlaps=[scores.ScoreAssembly(perm=
                                    data.OligoKPerm(kperm=
                                                    [oligos[i]
                                                     for i in scperm.permids]),
                                    ooverl=3).noverlaps(attr="kperm")
               for scperm in scperms]

    good_permid=[oligos.index(val) for val in sorted(oligos,key=lambda x:x.pos0)]
    print("correct permutation=",good_permid)
    correct_perms=[scperm for scperm in scperms if tuple(scperm.permids)==tuple(good_permid)]
    print("len(correct_perms)=",len(correct_perms))
    return pdfcosts,noverlaps,correct_perms,good_permid


if __name__=='__main__':
    #division0=pickle.load(open("full100bsubdivision_first_element_backup.pickle","rb"))
    #division=pickle.load(open("full100bsubdivision_backup.pickle","rb"))
    # collection0=division[0][0][0] is 7053120 times in division[0]
    division=pickle.load(open("per_subdivision_backup.pickle","rb"))
    
    

    # main problems:
    # problem reduction:
    # is there a way to tell without knowing the permutations or the oligo sequences
    # -> no outer_seqs (reminder , outerr_seqs was only used for ScoreFilter)
    # which are good, which are bad?
    # Check this I would need to have 1) pdfcost, noverlaps and permutations and sequence and see
    # where true solution lies
    # cannot rely only on noverlaps because of FPos and FNeg

    # Try to recover the correct order!
    # for 20p sequence and 2 exp pre. we can do the full calculus
    
    # for each merged we need to :
    # recompute the full pdfcost? 
    # no! too long. If all have same precision distribution,
    # we can rescale pdfcost such that unmoved oligopeaks have null cost.
    # for each kperm. numpy.log(density)-1

    # recompute the number of overlaps for the same reason

