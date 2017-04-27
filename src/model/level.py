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
    initial = 1 # type: int
    pull    = 3 # type: int
    measure = 5 # type: int
    count   = 8 # type: int
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
