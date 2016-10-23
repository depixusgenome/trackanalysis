#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"""
Classes defining a level of data treatment.
"""
from enum   import Enum, unique

@unique
class Level(Enum):
    u"Class containing configuration infos for a task"
    project = 0
    bead    = 1
    cycle   = 2
    event   = 3
    none    = None # type: ignore

def levelprop(val):
    u"Adds a read-only property"
    def _wrap(cls):
        cls.level = property(lambda _: val)
        return cls
    return _wrap
