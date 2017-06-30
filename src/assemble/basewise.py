#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import pickle
import assemble.piecewise as pw
import assemble.data as data
import assemble.scores as scores
import assemble._utils as utils
import itertools
from operator import attrgetter
import numpy

from typing import Tuple, List

# The Problem is that when we add permutation up until the index (or above)
# the full scaffolding of permutation is not entirely reconstructed
# before being scored and eventually discarded.
# What happens then is that optimal partition are not entirely reconstructed up until the index
# and discarded before having a chance to perform as well as the optimal



# to check that the score is computed on the correct index
def rank_by_noverlaps(partitions:List[List[data.OligoKPerm]],ooverl,index:int):
    # if we construct partitions index per index discarding those that are not optimal
    # we can limit to checking that the perm[index-1:index] do overlap
    scored=[]
    for part in partitions:
        merged=data.OligoPerm.add(*part)
        print("index=",index)
        print("merged.domain=",merged.domain)
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


def construct_scaffold(base:List[data.OligoPerm],
                       add_kperms:List[data.OligoKPerm],index:int)->List[List[data.OligoKPerm]]:
    u'''
    the base is the starting partition is expand up to index.
    ie until domain for merged base
    does not produce duplicates
    '''
    merged=data.OligoPerm.add(*base)
    if all(i in merged.domain for i in range(index)):
        return [base]

    # to continue
    next_id=min([idx for idx in range(index) if not idx in merged.domain])
    to_return=[]
    to_add=[kprm for kprm in add_kperms if not merged.domain.intersection(kprm.domain)
            and next_id in kprm.domain]
    for kprm in to_add:
        to_return+=construct_scaffold(base+[kprm],add_kperms,index)

    return to_return

def base_per_base(pwassemble):
    groupedids=utils.group_overlapping_normdists([oli.dist for oli in pwassemble.oligos])[1]    
    full_kperms=set([]) # can be updated sequentially
    for group in groupedids:
        full_kperms.update(set(pwassemble.find_kperms(group)))

    #pickle.dump(full_kperms,open("fullperms.pickle","wb"))
    #full_kperms=pickle.load(open("fullperms.pickle","rb"))
    add_kperms=[kpr for kpr in full_kperms if kpr.domain.intersection({0})]

    # for the first iteration,
    # we can keep only kpr if the 2 first oligos overlap kpr.perm[:2] or consist only of {0}
    add_kperms=[kpr for kpr in add_kperms if data.OligoPeak.tail_overlap(kpr.perm[0].seq,kpr.perm[1].seq)
                or len(kpr.domain)==1]
    partitions=[[kpr] for kpr in add_kperms]

    for index in range(1,len(pwassemble.oligos)):
        print("len(partitions)=",len(partitions))
        print("index=",index)
        add_kperms=[kpr for kpr in full_kperms if frozenset(kpr.permids).intersection({index})]
        print("len(add_kperms)=",len(add_kperms))
        added_partitions=[]
        for partidx,part in enumerate(partitions):
            #mx_idx=max([max(kpr.kpermids) for kpr in part])
            # before was checking that the max_idx was lower than<index to complement
            # instead always complement
            # if the partition is too short
            # then extend the partition until all indices<index are in domain
            # kpr in add_kperms which do not intersect with part
            #new_parts=construct_scaffold(part,[kpr for kpr in add_kperms
            #                                   if not any(prm.domain.intersection(kpr.domain)
            #                                              for prm in part)],index)
            new_parts=construct_scaffold(part,full_kperms,index)
            added_partitions+=new_parts

        print(len(added_partitions))
        ranked=rank_by_noverlaps(added_partitions,pwassemble.ooverl,index)
        max_overlap=max(i[0] for i in ranked)
        # compute the noverlaps of data.OligoPerm.add(*part).perm between 0 and i<index
        # keep only the partitions which have maximal noverlaps
        # too restrictive?
        #partitions=pwassemble.add2partitions(partitions,[[kpr] for kpr in add_kperms])
        partitions=[part for score,part in ranked if score==max_overlap]
    # for each base from 0 to len(oligos)-1
    # select all kperms which intersect this base
    # keep all partitions
    # we can discard a partition iff:
    # we know that no permutation will never affect oligos before i
    # and that the (merged) partitition up to i-1 has lower noverlaps 
    return partitions

if __name__=="__main__":
    oligos=pickle.load(open("oligohits.pickle","rb"))
    collection=data.BCollection.from_oligos(oligos)
    pwassemble=pw.PieceAssemble(collection=collection,ooverl=3)
    groupedids=utils.group_overlapping_normdists([oli.dist for oli in oligos])[1]
    add_kperms=[pwassemble.find_kperms(group) for group in groupedids]
    for addid,addkpr in enumerate(add_kperms):
        pickle.dump(addkpr,open("add_kperms"+str(addid)+".pickle","wb"))
        subkprm=[]
        for kpr in addkpr:
            subkprm+=find_subkperms_from_permids(oligos,kpr.kpermids)
        pickle.dump(list(set(subkprm)),open("subkprm"+str(addid)+".pickle","wb"))

        # need to take the set of subkperms because they will be many duplicates
        # __hash__ and __eq__ already implemented
