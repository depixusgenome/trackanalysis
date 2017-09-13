#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Classes defining a type of data treatment.

**Warning** Those definitions must remain data-independant.
"""
from pathlib        import Path
from typing         import Sequence, Dict, Tuple, Union, List

from utils          import initdefaults
from ..level        import Level
from .base          import Task, RootTask

_PATHTYPE = Union[str, Path, Tuple[Union[str,Path],...]]
PATHTYPE  = Union[_PATHTYPE, Dict[str,_PATHTYPE]]

class TrackReaderTask(RootTask):
    "Class indicating that a track file should be added to memory"
    def __init__(self,
                 path:      PATHTYPE = None,
                 beadsonly: bool     = False,
                 copy:      bool     = False, **kwa) -> None:
        super().__init__(**kwa)
        self.path      = path
        self.beadsonly = beadsonly
        self.copy      = copy

class CycleCreatorTask(Task):
    "Task for dividing a bead's data into cycles"
    levelin    = Level.bead
    levelou    = Level.cycle
    first: int = None
    last:  int = None
    @classmethod
    def unique(cls):
        "returns class or parent task if must remain unique"
        return cls

class DataSelectionTask(Task):
    "selects some part of the data"
    level                                  = Level.none
    beadsonly: bool                        = None
    samples:   Union[Sequence[int], slice] = None
    phases:    Union[Tuple[int,...], int]  = None
    selected:  List                        = None
    discarded: List                        = None
    cycles:    slice                       = None
    @initdefaults(frozenset(locals()) - {'level'})
    def __init__(self, **_) -> None:
        super().__init__()
