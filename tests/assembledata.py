#!/usr/bin/env python3
# -*- coding: utf-8 -*-

u''' tests OligoHit functions
'''

import assemble.data as data

OLIGOS=[data.OligoPeak() for i in range(4)]

def test_tail_overlap():
    u'''tests
    '''
    assert data.Oligo.tail_overlap("ATCG","ATCG")=="ATCG"
    assert data.Oligo.tail_overlap("AAAAATCG","ATCG")=="ATCG"
    assert data.Oligo.tail_overlap("ATCG","TCG")=="TCG"
    assert data.Oligo.tail_overlap("ATCG","CGTA")=="CG"
    assert data.Oligo.tail_overlap("ATCG","")==""
    assert data.Oligo.tail_overlap("","ATCG")==""
    assert data.Oligo.tail_overlap("ATCG","AtCG")==""
    assert data.Oligo.tail_overlap("atcg","atcg")=="atcg"
    assert data.Oligo.tail_overlap("atcg","ATcg")==""

def test_reverse_complement():
    u'''tests
    '''
    assert data.Oligo.reverse_complement("ATCG")=="CGAT"
    assert data.Oligo.reverse_complement("atcg")=="cgat"
    assert data.Oligo.reverse_complement("aTcg")=="cgAt"
    assert data.Oligo.reverse_complement("")==""

def testOligoKPerm():
    'to implement'
    # to implement!
    # emphasis on domain and span and the difference between the 2
    #kperm=data.OligoKPerm(oligos=OLIGOS,kperm=[OLIGOS[i] for i in range(4)])
    pass

def testOligoPerm():
    'to implement'
    # to implement!
    # emphasis on domain and span and the difference between the 2
    pass



def testPartitionsPaths():
    '''
    checks the creation and storage of paths for partitions
    '''
    # create oligos
    oligos=[data.OligoPeak(seq="",pos=i) for i in range(5)]
    # define some kperms which will lead to paths
    kprids=[[1,0],[1,2,0],[2],[3],[4]]

    kperms=[data.OligoKPerm(oligos=oligos,
                            kperm=[oligos[i] for i in kpr],
                            domain=frozenset(kpr)) for kpr in kprids]
    part0=data.Partition(perms=[kperms[0],kperms[2],kperms[3]])
    part1=data.Partition(perms=[kperms[1],kperms[3]])
    part2=data.Partition(perms=[kperms[1],kperms[3],kperms[4]])
    # check output, size of reduction and paths
    reduced=data.Partition.reduce_partitions([part0,part0],index=1)
    assert len(reduced)==1
    assert kperms[0] in reduced[0].perms
    assert kperms[2] in reduced[0].perms
    assert len(list(reduced[0].paths()))==1
    # len(reduced.ambi)==1 and each element is an empty partition
    reduced=data.Partition.reduce_partitions([part0,part1],index=3)
    assert len(reduced)==1
    assert len(list(reduced[0].paths()))==2
    part3=reduced[0]
    part3.add(perm=kperms[4],in_place=True)
    reduced=data.Partition.reduce_partitions([part2,part3],index=4)
    assert len(reduced)==1
    assert len(list(reduced[0].paths()))==2
