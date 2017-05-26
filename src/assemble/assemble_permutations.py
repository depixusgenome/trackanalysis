#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from typing import List, Set, Callable, NamedTuple, Tuple # pylint: disable=unused-import
import pickle
import time
import numpy
import functools
import itertools
import assemble.data as data
import assemble.scores as scores
# pylint: disable=invalid-name


def faster_merge_division2(division:List[List[scores.ScoredKPermCollection]],ooverl):
    u'''
    should replace merge_collections
    reduces the kpermcollection of each element in division to 1 KPermCollection
    before moving to the next one
    '''
    scfilter=scores.ScoreFilter(ooverl=ooverl)
    for idx,div in enumerate(division):
        print("idx=",idx)
        if len(div)==1:
            continue
        while len(div)>1:
            print("len(div)=",len(div))
            sckp1,sckp2=div[:2]
            merged=scores.ScoredKPermCollection.product(sckp1,sckp2)
            merged.sckperms=scfilter(merged.sckperms)
            for divi in division[idx:]:
                if sckp1 in divi and sckp2 in divi:
                    divi.remove(sckp1)
                    divi.remove(sckp2)
                    divi.append(merged)

    return division

def faster_merge_division(division:List[List[scores.ScoredKPermCollection]]):
    u'''
    should replace merge_collections
    Looks at the collections merging the most, 
    merges them apply it to all List having these collections
    '''
    set_coll = set(sckpc for divi in division for sckpc in divi)
    pickle.dump(division,open("division.pickle","wb"))
    while any(len(divi)>1 for divi in division):
        print("mean(len(divi))=",numpy.mean([len(divi) for divi in division]))
        # find the most common ScoredKPermCollection in divi of len>1 ->sckp1
        ranks=sorted(((len([divi for divi in division if sckp in divi and len(divi)>1]),sckp) for sckp in set_coll),
                     key=lambda x:x[0])

        sckp1 = ranks[-1][1]
        # find the next common ScoredKPermCollection which also have sckp1 ->sckp2
        ranks=list(([divi for divi in division if sckp in divi and sckp1 in divi],sckp)
                   for sckp in set_coll if sckp!=sckp1)
        ranks = sorted(ranks,key=lambda x:len(x[0]))
        sckp2 = ranks[-1][1]
        # merge sckp1 and sckp2 -> msckp
        merged=scores.ScoredKPermCollection.product(sckp1,sckp2)
        # for each sckperms in merged add the noverlaps
        # filter msckp -> msckp

        #merged.sckperms=scfilter(merged.sckperms) 
        pickle.dump(division,open("merging_division.pickle","wb"))
        # replace sckp1 and sckp2 by msckp in all division
        print("len(ranks[-1][0])=",len(ranks[-1][0]))
        for divi in ranks[-1][0]:
            divi.remove(sckp1)
            divi.remove(sckp2)
            divi.append(merged)
            set_coll=set_coll.union({merged})

    return division

def merge_collections(collections:List[data.KPermCollection],ooverl=3)->List[data.OligoPeakKPerm]:
    u'''
    each element in  collections is now supposed independant
    kpermutations can now be apply simultaneously to find best match (except for boundary effects)

    need to consider: 
    (1,2,3,4,5)+(7,8,9,10,11)
    when 6 is out, how do I score the noverlaps?
    No! that's the point of keeping track of outer sequences 
    '''

    score=scores.ScoreAssembly(ooverl=ooverl)
    scfilter=scores.ScoreFilter(ooverl=ooverl)

    scollections=[]
    for coll in collections:
        #scollections.append(scores.ScoredKPermCollection(sckperms=[scores.ScoredKPerm(kperm=kpm,
        #                                                                             pdfcost=scores.OptiKPerm(kperm=kpm.kperm).cost(),
        #                                                                             noverlaps=) for kpm in coll.kperms]))
        scollections.append(scores.ScoredKPermCollection(sckperms=[score(kpm) for kpm in coll.kperms]))

    #pickle.dump(scollections,open("scollections.pickle","wb"))
    #pickle.dump(collections,open("collections.pickle","wb"))

    merged=scores.ScoredKPermCollection.product(*scollections[:2])
    print("before, len(merged.sckperms)=",len(merged.sckperms))
    # for each sckperms in merged add the noverlaps
    # apply scorefilter
    merged.sckperms=scfilter(merged.sckperms)
    print("after, len(merged.sckperms)=",len(merged.sckperms))
    # and repeat
    for tocombine in scollections[2:]:
        merged=scores.ScoredKPermCollection.product(merged,tocombine)
        print("before, len(merged.sckperms)=",len(merged.sckperms))
        # apply scorefilter
        merged.sckperms=scfilter(merged.sckperms)
        print("after, len(merged.sckperms)=",len(merged.sckperms))


    # convert collections into ScoredKPermCollection
    # the product of any two ScoredKPerm is pdf1*pdf2 and OligoPeakKPerm.add(KPerm1,KPerm2)
    # then define the product of 2 ScoredKPermCollections
    # this leads to the calculation of pdfcost once per KPerm instead of each time 2 KPerms are added then scored
    
    # because the pdfcost is long to compute we can compute it once for each kperm in collections

    # per # of overlaps and outer_seq-
    # I need to find an condition
    # to restrict the number of kperms to the bare minimum.
    # each time 2 collections are merged, 

    # the following seems to work but is too long
    '''
    merged=data.KPermCollection.product(*collections[:2])
    print("before, len(merged.kperms)=",len(merged.kperms))
    score=scores.ScoreAssembly(ooverl=ooverl)
    scfiltre=scores.ScoreFilter(ooverl=ooverl)
    scmerged=[score(i) for i in merged.kperms] # pdfcost already computed
    # compute only the noverlaps
    merged.kperms=[i.kperm for i in scfiltre(scmerged)]
    print("after, len(merged.kperms)=",len(merged.kperms))
    for tocombine in collections[2:]:
        merged=data.KPermCollection.product(merged,tocombine)
        print("before, len(merged.kperms)=",len(merged.kperms))
        scmerged=[score(i) for i in merged.kperms]
        merged.kperms=[i.kperm for i in scfiltre(scmerged)]
        print("after, len(merged.kperms)=",len(merged.kperms))
    '''
    return merged

# needs to be modified  to use ScoredKPermCollections instead
def subdivide_then_partition(collections:List[scores.ScoredKPermCollection],
                             sort_by="kpermids",
                             max_size=25):
    u'''
    args:
    max_size argument is a tricky one.
    Until find_partitions is reimplemented, max_size can struggle for too high values.
    the bigger the max_size, the fewer the partitions to merge.
    find_partitions is too long for more than 30 KPermCollections
    Order the KPermCollection
    subdivide into 30 KPermCollection segments
    for each subdivision compute the partitions
    for each partition, merge the KPermCollection
        * each subdivision will have many partition, 
    ranking (deleting worse) partition should take place
        * the end result of the mergin is a new KPermCollection
    each kperm in the collection is a merge of multiple ones
    '''
    # order collection by indices (?) yes, could do
    # as long as we make sure that overlapping kpcs are together
    # !!!!!! it is not really possible to ensure that overlapping kpc are together since
    # !!!!!! they might be dependant 2 by 2
    # group intersecting kpcs? it is not a requirement IF are careful when merging
    ocollect = tuple(sorted(collections,key = lambda x:min(getattr(x.sckperms[0].kperm,sort_by))))
    print("len(ocollect)=",len(ocollect))
    subdivision=[tuple(ocollect[max_size*i:(i+1)*max_size])
                 for i in range(int(numpy.ceil(len(ocollect)/max_size)))]
    print("sumlentopart",sum(len(i)for i in subdivision))
    print("len of each partition ",list(len(i) for i in subdivision))
    per_subdivision=[]

    for subd in subdivision:
        partitions=[]
        seeds = [sckpc for sckpc in subd if sckpc.intersect_with(subd[0])]
        for seed in seeds:
            partitions.extend(find_partitions(seed,
                                              [sckpc for sckpc in subd
                                               if not sckpc.intersect_with(seed)]))
            # looking for duplicates
            
        per_subdivision.append(partitions)

    pickle.dump(per_subdivision,open("per_subdivision_backup.pickle","wb"))
    return per_subdivision

# seems to work correctly but is too long. memoisation problem? no!
# it appears that recursion is slow for python. Try a reimplementation using while loop
def find_partitions(part:scores.ScoredKPermCollection,
                    collections:List[scores.ScoredKPermCollection])->List[List[scores.ScoredKPermCollection]]:
    u'''
    part should not be in collections nor any collection which intersects with part
    recursive call
    '''
    if len(collections)==0:
        return []
    # look at each collection and see if they overlap with others
    intersections = list([i for i,v in enumerate(collections)
                          if kpc.intersect_with(v)] for kpc in collections)
    intersections = sorted(intersections,key=lambda x:len(x),reverse=True)
    # if they only overlap with themselves, then they can all be merged
    if len(intersections[0])==1:
        return [collections]

    return [[part]+toadd
            for i in intersections[0]
            for toadd in find_partitions(collections[i],
                                         [kpc for kpc in collections
                                          if not kpc.intersect_with(collections[i])])]


def reduce_collection(collection:data.KPermCollection)->data.KPermCollection:
    u'''
    score the kpermutations
    this function could potentially discard good (but unlikely) permutations
    need to check why some kperms have very high pdfcost 1e-5 when it should be neutral permutation
    '''
    score=scores.ScoreAssembly(ooverl=3)
    scored=[score(kperm) for kperm in collection.kperms]
    for sc in scored:
        print(sc.kperm.kpermids,sc.kperm.changes,sc.pdfcost,sc.noverlaps)
    scored=sorted(scored,key=lambda x:(x.pdfcost,x.noverlaps))
    print([i.pdfcost for i in scored])
    minpdfcost=min([x.pdfcost for x in scored])
    return data.KPermCollection(kperms=[scperm.kperm
                                        for scperm in scored
                                        if scperm.pdfcost/minpdfcost>0.5])


if __name__=='__main__':
    import pickle

    ooverl=3
    with open("filtered.pickle","rb") as testfile:
        filtered=pickle.load(testfile)

    print("len(filtered)=",len(filtered))

    # work on ScoreKPermCollection from here!

    # reduce each KPermCollection to the best ones pdfcost-wise not really useful as is
    #filtered = [reduce_collection(kpc) for kpc in filtered]
    # may create kpc with only neutral element
    #filtered = [kpc for kpc in filtered if len(kpc.kperms)>1]
    #with open("reduced.pickle","wb") as testfile:
    #    pickle.dump(filtered,testfile)


    # filtered: List[data.KpermCollection]
    score=scores.ScoreAssembly(ooverl=ooverl)

    scfilter=scores.ScoreFilter(ooverl=ooverl)

    scfiltered=[]
    for coll in filtered:
        scfiltered.append(scores.ScoredKPermCollection(sckperms=[score(kpm) for kpm in coll.kperms]))

    # creation of duplicates!!
    per_subdivision=subdivide_then_partition(scfiltered)
    per_subdivision=pickle.load(open("per_subdivision_backup.pickle","rb"))

    # per_subdivision is a List[List[List[KPermCollection]]]
    print("len(per_subdivision)=",len(per_subdivision))
    print("list(len(i) for i in per_subdivision)=",list(len(i) for i in per_subdivision))
    #for subd in per_subdivision:
    #    print("new subdivision to merge")
    #    for idx,collections in enumerate(subd):
    #        print("new collections merging ",idx)
    #        merged=merge_collections(collections)
    #        pickle.dump(merged,open("merged_subd.pickle","wb"))
    #        stop
    #pickle.dump(merge_collections,open("merge_collections.pickle","wb"))
    # merge collections
    # each kpc in a collection in  now independant and can be applied in any order
    
    # compute the scores
    # return the best

    # new faster way of merging the subdivisions
    merged=[]
    #for division in per_subdivision:
    #    merged.append(faster_merge_division2(division,ooverl=ooverl))
    ttime=time.time()
    #mtest=faster_merge_division2(per_subdivision[1],ooverl=ooverl)
    #print("faster_merge_division2 took:",time.time()-ttime)
    #pickle.dump(mtest,open("merged_division_backup.pickle","wb"))
    #pickle.dump(mtest,open("merged_division1_backup.pickle","wb"))
    merged=[pickle.load(open("merged_division_backup.pickle","rb")),pickle.load(open("merged_division1_backup.pickle","rb"))]
    # it appears that no collections in merged_division_backup.pickle intersect_with any of merged_division1_backup.pickle ...
    # but it will not be a general rule!
    merged_flat0=[lkpc[0] for lkpc in merged[0]]
    merged_flat1=[lkpc[0] for lkpc in merged[1]]
    ttime=time.time()
    full_merge=[scores.ScoredKPermCollection.product(first,second) for first,second in itertools.product(merged_flat0,merged_flat1)]
    #if not first.intersect_with(second)]
    print("fullmerging took",time.time()-ttime)
    pickle.dump(full_merge,open("full_merge.pickle","wb"))
    print(len(full_merge))
    stop
                       
