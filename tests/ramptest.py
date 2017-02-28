#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"tests opening, reading and analysis of a ramp.trk file"
#from   legacy import readtrack   # pylint: disable=import-error,no-name-in-module
from ramp           import RampModel, RampData
from testingcore    import path

def test_model():
    u''' tests that RampModel has the attributes for RampControler
    '''
    mod = RampModel()
    assert hasattr(mod,"scale")
    assert hasattr(mod,"needsCleaning")
    assert hasattr(mod,"corrThreshold")
    assert mod.needsCleaning is False

def test_readFromTrk():
    u'''
    check that RampControler can be initialised from a trk file
    '''
    mod = RampModel()
    mod.needsCleaning = False
    ramp = RampData.openTrack(path("ramp_legacy"),mod)
    beads = {i for i in range(56)}
    assert ramp.beads()==beads
    assert ramp.ncycles==13

def test_sanitize():
    u''' check that some beads are excluded from further analysis '''
    mod = RampModel()
    ramp = RampData.openTrack(path("ramp_legacy"),mod)
    ramp.clean()
    # largest set of good beads, i.e. no clean set should contain more than these
    lgoodbeads={2, 3, 6, 7, 8, 10, 13, 14, 16, 19, 23, 24, 25, 26, 27, 28, 29,
                30, 33, 35, 37, 38, 39, 41, 42, 43, 44, 45, 47, 48, 49, 50, 51, 52}
    print("lgoodbeads=",lgoodbeads)
    print("ramp.beads()=",ramp.beads())
    assert ramp.beads()&lgoodbeads == ramp.beads()

if __name__ == '__main__':
    test_sanitize()
