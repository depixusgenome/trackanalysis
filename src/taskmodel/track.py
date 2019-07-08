#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Classes defining a type of data treatment.

**Warning** Those definitions must remain data-independant.
"""
from pathlib import Path
from typing  import Sequence, Dict, Tuple, Union, List, Optional

from utils   import initdefaults
from .level  import Level
from .base   import Task, RootTask

_PATHTYPE = Union[str, Path, Tuple[Union[str,Path],...]]
PATHTYPE  = Union[_PATHTYPE, Dict[str,_PATHTYPE]]

class InMemoryTrackTask(RootTask):
    """
    directly the track file.

    Please don't use outside tests.
    """
    def __init__(self, track, **kwa) -> None:
        super().__init__(**kwa)
        self.track = track

class TrackReaderTask(RootTask):
    """
    Reads a track file to memory

    # Attributes

    * `path`: is the path to a track file and its optional secondary files
    * `copy`: only a copy of the data should be iterated over.
    * `key`: a name by which to call the track. Defaults to the filename.
    * `axis`: which axis to load, It can be "X" "Y" or "Z"
    """
    path: Optional[PATHTYPE] = None
    copy: bool               = False
    key:  Optional[str]      = None
    axis: str                = 'Z'
    def __init__(self, path = None, **kwa) -> None:
        super().__init__(**kwa)
        lst = 'path', 'key', 'axis'
        if hasattr(path, 'axis'):
            # Conversion for Track object
            kwa, tmp = {i: getattr(path, i) for i in lst}, kwa
            kwa.update(tmp)
        else:
            kwa['path'] = path

        for i in lst+('copy',):
            setattr(self, i, kwa.get(i, getattr(self.__class__, i)))

        # making sure the axis is a str
        self.axis = getattr(self.axis, 'name', self.axis)

class UndersamplingTask(Task):
    """
    Resample the track up to a given frequency.

    The resampling is exact: a track at 30Hz with a framerate at 9 or 11Hz will
    be resampled at 10Hz, i.e with 3 old frames per new frame
    """
    level:       Level = Level.bead
    framerate:   float = 30.
    aggregation: str   = 'mean'
    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        super().__init__(**_)

class CycleCreatorTask(Task):
    "Iterate over cycles and beads"
    levelin              = Level.bead
    levelou              = Level.cycle
    first: Optional[int] = None
    last:  Optional[int] = None
    @initdefaults(('first', 'last'))
    def __init__(self, **_) -> None:
        super().__init__()

    @classmethod
    def unique(cls):
        "returns class or parent task if must remain unique"
        return cls

class CycleSamplingTask(Task):
    """
    Replace the track with a new one containing only selected cycles.

    This must be applied just after the root task for it to be meaningful

    # Attributes

    * `cycles`: a slice or list of cycles to select.
    """
    cycles: Union[Sequence[int], slice, None] = None
    level                                     = Level.bead
    @initdefaults(frozenset(locals()) - {'level'})
    def __init__(self, **_) -> None:
        super().__init__()

class DataSelectionTask(Task):
    """
    Select some part of the data.

    # Attributes

    Some attributes are only relevant to `Beads` or to `Cycles` as indicated.

    * `samples`: a slice indicating which frames to select.
    * `phases`: interval of phases to select (`Cycles`).
    * `selected`: the beads (`Beads`) or beads and cycles (`Cycles`) to be selected.
    * `selected`: the beads (`Beads`) or beads and cycles (`Cycles`) to be selected.
    * `discarded`: the beads (`Beads`) or beads and cycles (`Cycles`) to be discarded.
    * `cycles`: the cycles to select (`Beads`).
    """
    level                                        = Level.none
    samples:   Union[None, Sequence[int], slice] = None
    phases:    Union[None, Tuple[int,...], int]  = None
    selected:  Optional[List]                    = None
    discarded: Optional[List]                    = None
    cycles:    Optional[slice]                   = None
    @initdefaults(frozenset(locals()) - {'level'})
    def __init__(self, **_) -> None:
        super().__init__()
