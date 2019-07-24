#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"""
Classes defining a level of data treatment.
"""
from dataclasses import dataclass
from enum        import Enum, unique
from typing      import Union, Tuple, Iterable, Iterator, Set, List, overload, cast

@unique
class InstrumentType(Enum):
    "The type of instrument"
    picotwist = "picotwist"
    sdi       = "sdi"
    muwells   = 'muwells'

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

PhaseArg   = Union[str, int]
PhaseRange = Tuple[PhaseArg, PhaseArg]

@dataclass
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
    initial:  int = 1
    pull:     int = 3
    rampdown: int = 4
    measure:  int = 5
    relax:    int = 7
    count:    int = 8

    @overload
    def __getitem__(self, value:PhaseArg) -> int:
        pass
    @overload
    def __getitem__(self, value:None) -> 'Phase':
        pass
    @overload
    def __getitem__(
            self,
            value:Union[List[PhaseArg], Tuple[PhaseArg], Set[PhaseArg], Iterator[PhaseArg]]
    ) -> List[int]:
        pass
    def __getitem__(self, value):
        return (
            self                     if value is Ellipsis  or value is None else
            getattr(self, value)     if isinstance(value, str)              else
            [self[i] for i in value] if isinstance(value, Iterable)         else
            cast(int, value)
        )

PHASE = Phase()

def levelprop(val):
    u"Adds a read-only property"
    def _wrap(cls):
        cls.level = property(lambda _: val)
        return cls
    return _wrap
