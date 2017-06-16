import pickle
import numpy
import time

from typing import List, Tuple
import itertools
from utils import initdefaults
import assemble.processor as processor
import assemble.scores as scores
import assemble.data as data
import assemble._utils as utils
import re

# to finish
class PiecewiseAssemble:
    u'''
    much faster version of assembler
    sequence is assembled sequentially starting from the first oligos
    adding iteratively groups of oligos which can permute
    '''
    nscale=1 # type: float
    collection=data.BCollection() # type: data.BCollection
    ooverl=1
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
        # find set of groups which are indepedent and partitions the set of oligos
        cores=[groupedids[0]] # partition the range of ids
        correctives={} # groups for correction
        for i in groupedids[1:]:
            if len(set(cores[-1]).intersection(i))==0:
                cores.append(i)
            else:
                try:
                    correctives[cores[-1]].append(i)
                except KeyError:
                    correctives[cores[-1]]=[i]
        assembled=[]
        # reconstruct 2 cores at a time
        test1=[]
        test2=[]
        partitions=[]
        # kperms of cores[1:-1] are computed twice, unnecessary
        last_only=False
        for idcore, core in enumerate(cores[1:]):
            if idcore>0:
                last_only=True
            # find the core permutations and the corrections permutations
            core_okperms,corr_okperms=self.find_kperms_coresandcorrs(cores=[cores[idcore],core],
                                                                     corrections=correctives[cores[idcore]])
            
            test1.append(core_okperms)
            test2.append(corr_okperms)

            # must be optimized, will change
            # find all ways to combine the permutations, 
            # There could be a better way to do that
            # if we look at each kperm in corr_okperms and see if there is a kperm which is better
            # we might miss combination of permutations
            # see if there is a combination (?) of permutations which is better
            partitions.append(self.find_kpermpartitions(core_okperms+corr_okperms))

            # add the kpermutations

            # rank combined kperms

        return test1,test2,partitions

    # to optimize, will be improved
    def find_kperms_coresandcorrs(self,
                                  cores:List[Tuple[int, ...]],
                                  corrections:List[Tuple[int, ...]])->List[data.OligoPerm]:
        u'''
        finds the permutations of oligos in cores
        and permutations from corrections (changed indices must be in both core_groups)
        '''
        idsperbatch=self.collection.idsperbatch
        batchfilter=processor.BetweenBatchFilter(idsperbatch=idsperbatch)
        ooverlfilter=processor.RequireOverlapFilter(oligos=self.oligos,
                                                    min_ooverl=self.ooverl)
        core_okperms=[]
        for core in cores:
            # compute all possible permutations # brute force
            permids=itertools.permutations(core) # generator
            firstfiltered = filter(ooverlfilter,permids) # type: ignore
            secondfiltered = filter(batchfilter,firstfiltered) # type: ignore
            for permid in secondfiltered:
                core_okperms.append(data.OligoKPerm(oligos=self.oligos,
                                                    kperm=[self.oligos[i] for i in permid],
                                                    kpermids=permid))
        corr_okperms=[]
        for corr in corrections:
            # compute all possible permutations # brute force
            permids=itertools.permutations(corr) # generator
            firstfiltered = filter(ooverlfilter,permids) # type: ignore
            secondfiltered = filter(batchfilter,firstfiltered) # type: ignore
            for permid in secondfiltered:
                corr_okprm=data.OligoKPerm(oligos=self.oligos,
                                           kperm=[self.oligos[i] for i in permid],
                                           kpermids=permid)
                if corr_okprm.domain.intersection(set(cores[0]))\
                   and corr_okprm.domain.intersection(set(cores[1])):
                    corr_okperms.append(corr_okprm)

            
        return core_okperms,list(set(corr_okperms))

    # ooverl will eventually be be the minimal number of overlapping 
    def test_find_kperms(self,oligos:List[data.OligoPeak],
                         ooverl=1:int,
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
            kperms+=[[oligos[:oliid]+oligos[oliid+1:] ]]
        return kperms
    
    def find_kpermpartitions(self,kperms):
        u'''
        finds the kperms which can be combined
        '''
        parts=[]
        seeds = [kperms[0]]+[kpr for kpr in kperms[1:] if kpr.domain.intersection(kperms[0].domain)]
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

    # not used 
    def assemble_groupedids(self,groupedids:List[List[int]])->List[List[int]]:
        u'''
        uset is the output of utils.group_overlapping_normdist [1]
        '''
        # find all groupedids intersecting with uset[0]
        inter=[]
        for i in range(len(groupedids)):
            if len(set(groupedids[i]).intersection(groupedids[0]))>0:
                inter.append(i)
            else:
                break
        # ... and the first uset independent with 0
        indep=inter[-1]+1 # groupedids should be sorted by construction
        # compute all kperms in groupedids[0] and groupedids[indep]
        # compute kperms in groupedids[i] for i in inter if they have both indices from 0 and indep
        # find possible combinations of kperm using subdivide_and_partition
        # rank

        # resume with new values of inter[] (previous value of indep) and new value of indep 

        return [[]]



    
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

