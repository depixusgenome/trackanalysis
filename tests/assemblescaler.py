#!/usr/bin/env python3
# -*- coding: utf-8 -*-

'''
tests the assemble.scaler submodule
'''

import assemble.scaler as scaler
import assemble.data as data

SEQUENCE="tgaagtgtga"

OLIGOS=[data.OligoPeak(pos=0.0,pos0=4.4,seq="gtg",poserr=4.5),
        data.OligoPeak(pos=1.1,pos0=3.3,seq="agt",poserr=4.5),
        data.OligoPeak(pos=2.2,pos0= 0.0,seq= "tga",poserr=4.5),
        data.OligoPeak(pos=3.3,pos0= 1.1,seq= "gaa",poserr=4.5),
        data.OligoPeak(pos=4.4,pos0= 2.2,seq= "aag",poserr=4.5),
        data.OligoPeak(pos=5.5,pos0= 5.5,seq= "tgt",poserr=4.5),
        data.OligoPeak(pos=7.7,pos0= 7.7,seq= "tga",poserr=4.5)]


MIN_OVERL=2

EXP_OLIGOS=scaler.no_orientation(OLIGOS)
PEAKS=scaler.OPeakArray.from_oligos(EXP_OLIGOS)
PEAKS=sorted(PEAKS,key=lambda x:-len(x.arr))


STACKER=scaler.Scaler(oligos=OLIGOS,
                      bbias=scaler.Bounds(-1.1,1.1),
                      bstretch=scaler.Bounds(0.95,1.05),
                      min_overlap=MIN_OVERL)


def test_cpaths():
    'checks creation of cyclic paths'
    graph=scaler.OPeakArray.list2graph(PEAKS,min_overl=MIN_OVERL)
    cpaths=list(scaler.cyclic_paths(graph,source=PEAKS[0]))
    cpaths=sorted(cpaths,key=len)
    assert all([len(path) in {3,6} for path in cpaths])
    # check that the path are actually cyclic
    for path in cpaths:
        assert PEAKS[0]==path[0]
        assert PEAKS[0]==path[-1]

    neighbours=scaler.OPeakArray.may_overlap(PEAKS[0],
                                             PEAKS[1:],
                                             min_overl=MIN_OVERL)

    # that the minimal ones contain closest neighbours
    assert neighbours[0] in cpaths[0] or neighbours[0] in cpaths[1]
    assert neighbours[1] in cpaths[0] or neighbours[1] in cpaths[1]

    # no peakarrays contains the aca peak
    uni=frozenset().union(*[frozenset(path) for path in cpaths])
    notin=frozenset(PEAKS)-uni
    assert len(notin)==1
    assert list(notin)[0].arr[0].seq=="aca"
    # maximal ones contains the greater cycles in different orders
    # eg: (1,2,3,1) and (1,3,2,1)


# needs to
# * stack without rescaling since stretch bias bounds are defined from original stretch
# * allow for reverse seq for stack(key) when stacking upon
# * must find at least 1 cpath which partially reconstructs the sequence
# * consider any paths of incremental size?
# * should start with cyclic paths, resolve the conflicts there
# * then add all (iteratively) PEAKS which  have not been fixed with cyclic paths
def test_stack():
    'test proper stacking of cpaths'
    graph=scaler.OPeakArray.list2graph(PEAKS,min_overl=MIN_OVERL)
    cpaths=list(scaler.cyclic_paths(graph,source=PEAKS[0]))
    cpaths=sorted(cpaths,key=len)

    # find possible scaledpaths (fix issue with build_stacks and build_stacks_fromtuple)
    stack=scaler.PeakStack()
    stack.add(PEAKS[0])
    # to continue from here
    #scaledpaths=[STACKER.build_stacks_fromtuple(stack,path) for path in cpaths]
