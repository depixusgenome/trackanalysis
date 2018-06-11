#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Tests carryover detection"

import pandas as pd

from scripting import carryover

CARRY = carryover.CarryOver(cleanprop=0.6)

DATA = pd.DataFrame(dict(track = ["agt","agt","atc","tga","ccc","ggg","ttt"],
                         peakposition = [0.001,0.002,0.003,0.008,0.009,0.000,0.01],
                         eventcount   = [60,10,3,20,10,2,1],
                         modification = [pd.Timestamp(i) for i in range(7)]))
DATA = DATA.sort_values("track")

def test_nooverlap():
    "close should not overlap"
    names = [("tca","agt"),("ccc","ggg"),("cca","aca")]

    for first, second in names:
        print(f"{first,second}")
        assert CARRY.rulenooverlap({"track":first},{"track":second})

    names=[("agc","agc"),("agc","gct"),("agc","tag")]
    for first, second in names:
        assert not CARRY.rulenooverlap({"track":first},{"track":second})


def test_fewerevents():
    "fewer events after cleaning"
    assert not CARRY.rulefewerevents({"eventcount":10},{"eventcount":7})
    assert CARRY.rulefewerevents({"eventcount":10},{"eventcount":6})
    assert CARRY.rulefewerevents({"eventcount":10},{"eventcount":1})

def test_find():
    "check pairs found"
    pairs = list(CARRY.find(DATA))
    assert len(pairs)==2
    names = [tuple(i["track"] for i in pair) for pair in pairs]
    assert ("agt","atc") in names
    assert ("tga","ccc") in names

if __name__ == "__main__":
    test_nooverlap()
