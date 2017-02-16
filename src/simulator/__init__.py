#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Simulation of tracks or other types of data"
from .track import TrackSimulator
from .peak  import PeakSimulator

def randbead(seed = None, **kwa):
    u"Random bead. See TrackSimulator documentation"
    return TrackSimulator(**kwa)(seed)

def randtrack(nbeads = 1, seed = None, **kwa):
    u"Random track. See TrackSimulator documentation"
    return TrackSimulator(**kwa).track(nbeads, seed)

def randpeaks(ncycles = 1, seed = None, **kwa):
    u"Random peaks. See PeakSimulator documentation"
    return PeakSimulator(**kwa)(ncycles, seed)
