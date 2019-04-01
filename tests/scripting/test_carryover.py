#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Tests carryover detection"
from   tests.testutils import integrationmark
import pandas as pd

@integrationmark
def test_nooverlap(holoviewingcleaner):
    "close should not overlap"
    from scripting import carryover # pylint: disable=import-error,wrong-import-position

    CARRY = carryover.CarryOver(cleanprop=0.6)
    DATA = pd.DataFrame(dict(track = ["agt","agt","atc","tga","ccc","ggg","ttt"],
                             peakposition = [0.001,0.002,0.003,0.008,0.009,0.000,0.01],
                             eventcount   = [60,10,3,20,10,2,1],
                             modification = [pd.Timestamp(i) for i in range(7)]))
    DATA = DATA.sort_values("track")
    names = [("tca","agt"),("ccc","ggg"),("cca","aca")]

    for first, second in names:
        print(f"{first,second}")
        assert CARRY.rulenooverlap({"track":first},{"track":second})

    names=[("agc","agc"),("agc","gct"),("agc","tag")]
    for first, second in names:
        assert not CARRY.rulenooverlap({"track":first},{"track":second})

@integrationmark
def test_fewerevents(holoviewingcleaner):
    "fewer events after cleaning"
    from scripting import carryover # pylint: disable=import-error,wrong-import-position

    CARRY = carryover.CarryOver(cleanprop=0.6)

    DATA = pd.DataFrame(dict(track = ["agt","agt","atc","tga","ccc","ggg","ttt"],
                             peakposition = [0.001,0.002,0.003,0.008,0.009,0.000,0.01],
                             eventcount   = [60,10,3,20,10,2,1],
                             modification = [pd.Timestamp(i) for i in range(7)]))
    DATA = DATA.sort_values("track")
    assert not CARRY.rulefewerevents({"eventcount":10},{"eventcount":7})
    assert CARRY.rulefewerevents({"eventcount":10},{"eventcount":6})
    assert CARRY.rulefewerevents({"eventcount":10},{"eventcount":1})

@pytest.mark.xfail
@integrationmark
def test_find(holoviewingcleaner):
    "check pairs found"
    from scripting import carryover # pylint: disable=import-error,wrong-import-position

    CARRY = carryover.CarryOver(cleanprop=0.6)

    DATA = pd.DataFrame(dict(track = ["agt","agt","atc","tga","ccc","ggg","ttt"],
                             peakposition = [0.001,0.002,0.003,0.008,0.009,0.000,0.01],
                             eventcount   = [60,10,3,20,10,2,1],
                             modification = [pd.Timestamp(i) for i in range(7)]))
    DATA = DATA.sort_values("track")
    pairs = list(CARRY.find(DATA))
    assert len(pairs)==2
    names = [tuple(i["track"] for i in pair) for pair in pairs]
    assert ("agt","atc") in names
    assert ("tga","ccc") in names

if __name__ == "__main__":
    test_nooverlap()
