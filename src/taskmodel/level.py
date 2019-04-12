#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"""
Classes defining a level of data treatment.
"""
from enum   import Enum, unique
from utils  import initdefaults

class InstrumentType(Enum):
    "The type of instrument"
    picotwist = "picotwist"
    sdi       = "sdi"
    muwells   = 'µwells'

@unique
class Level(Enum):
    """
    Indicates stages at which a task is performed

    * `project`: all beads can be affected at together.
    * `bead`: each bead is worked on independently.
    * `cycle`: each bead cycle is worked on independently.
    * `event`: same as cycle, but with hybridisation events already extracted.
    * `peak`: events have been grouped by peak. The work occurs on each bead independently.
    * `none`: the stage is unspecified
    """
    project = 0
    bead    = 1
    cycle   = 2
    event   = 3
    peak    = 4
    none    = None # type: ignore

class Phase:
    """
    Phase names in a cycle. Labeled phases are characterized by a stable magnet
    height.  Each of them is preceeded and followed by a phase where the magnet
    height is changed.

    The following describes the usual situation:

    * `initial`: phase 1 should be at the same magnet height (~10 pN of force) as
    `measure`. It could be used as a reference point.
    * `pull`: phase 3 is when the magnet is at the closest from the
    sample (18 pN of force). This is when a hairpin should unzip.
    * `measure`: phase 5 is when hybridisation events are measured (10 pN of force).
    * `relax`: phase 7 is used to remove probes from the hairpin.  The magnet
    is then at its farthest point (5 pN of force).
    """
    initial  = 1
    pull     = 3
    rampdown = 4
    measure  = 5
    relax    = 7
    count    = 8
    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        pass
PHASE = Phase()

def levelprop(val):
    u"Adds a read-only property"
    def _wrap(cls):
        cls.level = property(lambda _: val)
        return cls
    return _wrap
