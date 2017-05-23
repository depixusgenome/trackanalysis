#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from typing import List, Set, Callable, NamedTuple, Tuple # pylint: disable=unused-import
import numpy
import functools
import itertools
import assemble.data as data
import assemble.scores as scores
# pylint: disable=invalid-name

def merge_collections(collections:List[data.KPermCollection],ooverl=3)->List[data.OligoPeakKPerm]:
    u'''
    each element in  collections is now supposed independant
    kpermutations can now be apply simultaneously to find best match (except for boundary effects)
    '''

    scollections=[]
    for coll in collections:
        scollections.append(scores.ScoredKPermCollection(sckperm=[Scores.ScoredKPerm(kperm=kpm.kperm,pdfcost=OptiKPerm(kperm=kpm.kperm).cost()) for kpm in coll.kperms]))

    scfilter=scores.ScoreFilter(ooverl=ooverl)

    merged=scores.ScoredKPermCollection.product(*scollection[:2])
    print("before, len(merged.kperms)=",len(merged.kperms))
    # for each sckperms in merged add the noverlaps
    merged=scores.ScoredKPermCollection.product(*scollection[:2])
    # apply scorefilter
    merged.sckperms=scfilter(merged.sckperms)
    # and repeat
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
    return merged

def subdivide_then_partition(collections:List[data.KPermCollection],sort_by="kpermids",max_size=25):
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
    ocollect = tuple(sorted(collections,key = lambda x:min(getattr(x.kperms[0],sort_by))))
    print("len(ocollect)=",len(ocollect))
    subdivision=[tuple(ocollect[max_size*i:(i+1)*max_size])
                 for i in range(int(numpy.ceil(len(ocollect)/max_size)))]
    print("sumlentopart",sum(len(i)for i in subdivision))
    print("len of each partition ",list(len(i) for i in subdivision))

    per_subdivision=[]
    for subd in subdivision:
        partitions=[]
        seeds = [kpc for kpc in subd if kpc.intersect_with(subd[0])]
        for seed in seeds:
            partitions.extend(find_partitions(seed,
                                              [kpc for kpc in subd
                                               if not kpc.intersect_with(seed)]))
        per_subdivision.append(partitions)


    pickle.dump(per_subdivision,open("per_subdivision_backup.pickle","wb"))
    # for each partition, get seeds.
    # compute the partitions for each seed

    return per_subdivision

# seems to work correctly but is too long. memoisation problem? no!
# it appears that recursion is slow for python. Try a reimplementation using while loop
def find_partitions(part:data.KPermCollection,
                    collections:List[data.KPermCollection])->List[List[data.KPermCollection]]:
    u'''
    part should not be in collections nor any collection which intersects with part
    recursive call
    kpseed is a kpermcollection
    collections in a list of kpermcollection
    returns duplicated results with part:data.KPermCollection
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
    this function could potentially discard good (but likely) permutations
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
    with open("filtered.pickle","rb") as testfile:
        filtered=pickle.load(testfile)

    print("len(filtered)=",len(filtered))
    #filtered=filtered[-30:]
    
    # reduce each KPermCollection to the best ones pdfcost-wise
    filtered = [reduce_collection(kpc) for kpc in filtered]
    # may create kpc with only neutral element
    filtered = [kpc for kpc in filtered if len(kpc.kperms)>1]
    #print("filtered=",filtered)
    with open("reduced.pickle","wb") as testfile:
        pickle.dump(filtered,testfile)

    #per_subdivision=subdivide_then_partition(filtered)
    per_subdivision=pickle.load(open("per_subdivision_backup.pickle","rb"))

    # per_subdivision is a List[List[List[KPermCollection]]]
    for subd in per_subdivision:
        print("new subdivision to merge")
        for idx,collections in enumerate(subd):
            print("new collections merging ",idx)
            merge_collections(collections)
    # merge collections
    # each kpc in a collection in  now independant and can be applied in any order
    
    # compute the scores
    # return the best

    stop
    # alternate take.
    # 2 intersecting collections cannot be chosen simultaneously
    # compare intersecting collections.
    score=scores.ScoreAssembly(ooverl=3)
    for kpc in seeds:
        print(kpc)
        for kpm in kpc.kperms:
            print(kpm.kpermids,score(kpm).noverlaps,score(kpm).pdfcost)
                       
