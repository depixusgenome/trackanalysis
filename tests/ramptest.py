#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u""" Tests ramp analysis """
#from   legacy import readtrack   # pylint: disable=import-error,no-name-in-module
from data import Track
from ramp import RampModel, RampControler
from testdata import path

# pylint: disable=no-self-use


class TestRamp:
    u"tests opening, reading and analysis of a ramp.trk file"
    def test_model(self):
        u''' tests that RampModel has the attributes for RampControler
        '''
        mod = RampModel()
        assert hasattr(mod,"scale")
        assert hasattr(mod,"needsCleaning")

    def test_readFromFile(self):
        u'''
        check that RampControler can be initialised from a file
        '''
        mod = RampModel()
        mod.needsCleaning = False
        ramp = RampControler.fromFile(path("ramp_legacy"),mod)
        beads = {i for i in range(56)}
        assert ramp.beads==beads
        assert ramp.ncycles==13

    def test_readFromTrack(self):
        u'''
        check that RampControler can be initialised from a Track object
        '''
        mod = RampModel()
        mod.needsCleaning = False
        beads = {i for i in range(56)}
        track = Track(path=path("ramp_legacy"))
        ramp = RampControler.fromTrack(track,mod)
        assert ramp.beads==beads
        assert ramp.ncycles==13

    def test_sanitise(self):
        u''' check that some beads are excluded from further analysis '''
        mod = RampModel()
        mod.needsCleaning = True
        ramp = RampControler.fromFile(path("ramp_legacy"),mod)
        # largest set of good beads, i.e. no clean set should contain more than these
        lgoodbeads={2, 3, 6, 7, 8, 10, 13, 14, 16, 19, 23, 24, 25, 26, 27, 28, 29,
                    30, 33, 35, 37, 38, 39, 41, 42, 43, 44, 45, 47, 48, 49, 50, 51, 52}
        assert ramp.beads&lgoodbeads == ramp.beads

