#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Monkey patches the Track class.

We add some methods and change the default behaviour:

* *__init__* takes *path* as it's first positional argument
* an *events* property is added
* a *rawprecision* method is added
"""
from typing                 import List
from pathlib                import Path
from datetime               import datetime

from utils.decoration       import addto, addproperty
from utils.attrdefaults     import addattributes
from model                  import PHASE
from model.__scripting__    import Tasks
from signalfilter           import PrecisionAlg

from ..track                import Track, LazyProperty

@addproperty(Track, 'pathinfo')
class PathInfo:
    """
    Provides information on the path itself:

        * `paths`: a tuple of paths
        * `trackpath`: the main path, i.e. not the grs
        * `size` (*megabytes*) is the size in bytes (megabytes) of *trackpath*
        * `stat`: stats on the *trackpath*
        * `modification`: the date oflast modification. This is basically the
        time of experiment.
        * `creation`: the creation date. **DISCARD** when using PicoTwist tracks.
    """
    def __init__(self, trk: 'Track') -> None:
        self._trk = trk

    @property
    def paths(self) -> List[Path]:
        "returns all paths"
        path = self._trk.path
        if isinstance(path, str):
            return [Path(path)]
        if isinstance(path, Path):
            return [path]
        return [Path(str(i)) for i in path]

    @property
    def trackpath(self) -> Path:
        "returns all paths"
        path = self._trk.path
        return Path(str(path[0])) if isinstance(path, (list, tuple)) else Path(str(path))

    pathcount    = property(lambda self: len(self.paths))
    stat         = property(lambda self: self.trackpath.stat())
    size         = property(lambda self: self.stat.st_size)
    megabytes    = property(lambda self: self.size >> 20)
    creation     = property(lambda self: datetime.fromtimestamp(self.stat.st_ctime))
    modification = property(lambda self: datetime.fromtimestamp(self.stat.st_mtime))

@addto(Track)
def rawprecision(self, ibead):
    "the raw precision for a given bead"
    if isinstance(ibead, (tuple, list)):
        ibead = next(i for i in ibead if isinstance(i, int))
    return PrecisionAlg.rawprecision(self, ibead)

@addto(Track)
def tasklist(self, *args, beadsonly = True):
    "creates a tasklist"
    return Tasks.tasklist(self.path, *args, beadsonly = beadsonly)

@addto(Track)
def processors(self, *args, copy = True, beadsonly = True):
    "returns an iterator over the result of provided tasks"
    procs = Tasks.processors(self.path, *args, beadsonly = beadsonly)
    procs.data.setCacheDefault(0, self)
    procs.copy = copy
    return procs

@addto(Track)
def apply(self, *args, copy = True, beadsonly = True):
    "returns an iterator over the result of provided tasks"
    return next(iter(self.processors(*args, beadsonly = beadsonly).run(copy = copy)))

@addto(Track) # type: ignore
@property
def cleancycles(self):
    "returns cleaned cycles"
    return self.apply(*Tasks.defaulttasklist(self, Tasks.alignment))[...,...]

@addto(Track) # type: ignore
@property
def measures(self):
    "returns cleaned cycles for phase 5 only"
    return self.cleancycles.withphases(PHASE.measure)

Track.cleaned = LazyProperty('cleaned')
addattributes(Track, protected = dict(cleaned = False))

Track.__doc__   += '* `pathinfo` p'+PathInfo.__doc__[5:]
Track.cycles    .args['copy'] = True
Track.cyclesonly.args['copy'] = True
Track.beads     .args['copy'] = True
Track.beadsonly .args['copy'] = True

__all__ = ['Track']
