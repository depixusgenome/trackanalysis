#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u""" Tests legacy data """

import legacy
from   testdata import path

def test_opentrack_big():
    u"test a big track file"
    trk  = legacy.readtrack(path("big_legacy"))
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
    trk  = legacy.readtrack(path("small_legacy"))
    assert trk['cyclemin']   == 3
    assert trk['cyclemax']   == 3
    assert trk['nphases']    == 8
    assert trk['t'].size     == 498
    assert trk['zmag'].size  == 498
    for i in range(39):
        assert trk[i].size == 498
    assert (frozenset(x for x in trk if isinstance(x, int))
            == frozenset([x for x in range(92)]))

def test_opentrack_missing():
    u"test a missing track file"
    trk  = legacy.readtrack("___non__existant__track.trk")
    assert trk is None
