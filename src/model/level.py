#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"""
Classes defining a level of data treatment.
"""
from enum   import Enum, unique
from utils  import initdefaults

@unique
class Level(Enum):
    u"Class containing configuration infos for a task"
    project = 0
    bead    = 1
    cycle   = 2
    event   = 3
    peak    = 4
    none    = None # type: ignore

class Phase:
    "Class containing default phases"
    initial = 1
    pull    = 3
    measure = 5
    relax   = 7
    count   = 8
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
