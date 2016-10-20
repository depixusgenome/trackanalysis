#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"""
Classes defining a level of data treatment.
"""
from enum   import Enum, unique

@unique
class Level(Enum):
    u"Class containing configuration infos for a task"
    base    = 0
    project = 100
    track   = 200
    bead    = 300
    cycle   = 400
    event   = 500

def levelprop(val):
    u"Adds a read-only property"
    def _wrap(cls):
        cls.level = property(lambda _: val)
        return cls
    return _wrap
