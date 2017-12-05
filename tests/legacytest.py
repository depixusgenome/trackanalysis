#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u""" Tests legacy data """

from legacy         import readtrack, readgr # pylint: disable=import-error,no-name-in-module
from testingcore    import path

def test_opengr():
    u"test a .gr file"
    ret = readgr(path("grfile.gr"))
    assert ret['title'] == (b'\\stack{{Bead 0 Z(t) 10}'
                            b'{\\pt7 Cycles:[3,104] phase(s) [1,2,3,4,5,6,7]}}')
    assert len(ret) == 101
    key = (b'Bead Cycle 95 phase(s): [1,2,3,4,5,6,7] '
           b'tracking at xx Hz Acquistion 10 for bead 0 \n'
           b' Z coordinate l = xx, w = xx, nim = xx\n')
    assert len(ret[key]) == 2
    assert len(ret[key][0]) == 448
    assert len(ret[key][1]) == 448
    assert str(ret[key][0].dtype) == 'float32'
    assert str(ret[key][1].dtype) == 'float32'

def test_opengr_bugged():
    u"tests opening incorrect or missing grs"
    assert readgr("does_not_exist.gr") is None
    assert readgr(path("small_legacy")) is None

def test_opentrack_big():
    u"test a big track file"
    trk  = readtrack(path("big_legacy"))
    assert trk['cyclemin']  == 3
    assert trk['cyclemax']  == 104
    assert trk['nphases']   == 8
    assert trk['t'].size    == 49802
    assert trk['zmag'].size == 49802
    for i in range(39):
        assert trk[i].size  == 49802
    assert (frozenset(x for x in trk if isinstance(x, int))
            == frozenset([x for x in range(39)]))

def test_opentrack_small():
    u"test a small track file"
    trk  = readtrack(path("small_legacy"))
    assert trk['cyclemin']   == 3
    assert trk['cyclemax']   == 3
    assert trk['nphases']    == 8
    assert trk['t'].size     == 498
    assert trk['zmag'].size  == 498
    for i in range(39):
        assert trk[i].size == 498
    assert (frozenset(x for x in trk if isinstance(x, int))
            == frozenset([x for x in range(92)]))

def test_opentrack_bugged():
    u"tests opening incorrect or missing trks"
    try:
        readtrack("does_not_exist.trk")
    except OSError:
        pass
    assert readtrack(path("grfile.gr")) is None

if __name__ == '__main__':
    test_opengr()
