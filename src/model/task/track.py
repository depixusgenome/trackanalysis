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
    path:      PATHTYPE = None
    beadsonly: bool     = False
    copy:      bool     = False
    key:       str      = None
    axis:      str      = 'Z'
    def __init__(self, path = None, **kwa) -> None:
        super().__init__(**kwa)
        lst = 'path', 'beadsonly', 'copy', 'key', 'axis'
        if hasattr(path, 'axis'):
            # Conversion for Track object
            kwa, tmp = {i: getattr(path, i) for i in lst}, kwa
            kwa.update(tmp)
        else:
            kwa['path'] = path

        for i in lst:
            setattr(self, i, kwa.get(i, getattr(self.__class__, i)))

        # making sure the axis is a str
        self.axis = getattr(self.axis, 'value', self.axis)

class CycleCreatorTask(Task):
    "Task for dividing a bead's data into cycles"
    levelin    = Level.bead
    levelou    = Level.cycle
    first: int = None
    last:  int = None
    @initdefaults(('first', 'last'))
    def __init__(self, **_) -> None:
        super().__init__()

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
