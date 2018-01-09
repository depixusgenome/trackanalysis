#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Monkey patches the Track class.

We add some methods and change the default behaviour:

* *__init__* takes *path* as it's first positional argument
* an *events* property is added
* a *rawprecision* method is added
"""
from   copy                 import copy  as shallowcopy
from   datetime             import datetime
from   functools            import partial
from   pathlib              import Path
from   typing               import List

import numpy                as     np

from   utils.decoration     import addto, addproperty
from   utils.attrdefaults   import addattributes
from   model                import PHASE, Task
from   model.__scripting__  import Tasks
from   signalfilter         import PrecisionAlg

from   ..trackio            import savetrack
from   ..track              import Track, LazyProperty, BEADKEY, isellipsis
from   ..trackops           import (selectbeads, dropbeads, selectcycles,
                                    concatenatetracks, renamebeads)
from   .tracksdict          import TracksDict

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
    return self.cleanbeads[...,...]

@addto(Track) # type: ignore
@property
def cleanbeads(self):
    "returns cleaned beads"
    return self.apply(*Tasks.defaulttasklist(self, Tasks.alignment))

@addto(Track) # type: ignore
@property
def measures(self):
    "returns cleaned cycles for phase 5 only"
    return self.cleancycles.withphases(PHASE.measure)

@addproperty(Track, 'op')
class TrackOperations:
    """
    A number of helper functions for selecting/discarding beads and cycles or
    concatenating files:

        * `track.op.save("path")` saves the track
        * `track.op.concatenate(track2, track3)` concatenates 3 experiments
        * `track.op + track2` concatenates 2 experiments
        * `del track.op[[1,3]]` deletes beads 1 and 3
        * `track.op.beads[[1,3]]` returns track with only beads 1 and 3
        * `track.op.beads[[1,3], [1,5]]` returns track with only beads 1 and 3, cycles 1 and 5
        * `track.op.beads[:, 1:5]` returns track with all beads 1 and cycles 1 to 5
    """
    def __init__(self, trk):
        self._trk = trk

    class _Add:
        def __init__(self, fcn):
            self._fcn    = fcn
            self.__doc__ = fcn.__doc__

        def __get__(self, instance, owner):
            return self._fcn if instance is None else partial(self._fcn, instance)

    concatenate  = _Add(concatenatetracks)
    save         = _Add(savetrack)
    rename       = _Add(renamebeads)

    def __add__(self, other):
        return self.concatenate(getattr(other, '_trk', other))

    def drop(self, *beads: BEADKEY) -> Track:
        """
        Drops beads
        """
        return self.__delitem__(list(beads))

    def __delitem__(self, beads) -> Track:
        if isinstance(beads, list):
            return dropbeads(self._trk, *beads)
        if np.isscalar(beads):
            return dropbeads(self._trk, beads)
        raise NotImplementedError()

    def __getitem__(self, beads) -> Track:
        if isinstance(beads, list):
            return selectbeads(self._trk, *beads)

        if np.isscalar(beads):
            return selectbeads(self._trk, beads)

        if isinstance(beads, tuple):
            if len(beads) != 2:
                raise KeyError("Key should be a (beads, cycles) tuple")
            trk = self._trk if isellipsis(beads[0]) else self.__getitem__(beads[0])
            trk = trk      if isellipsis(beads[1]) else selectcycles(trk, beads[1])
            return shallowcopy(self._trk) if trk is self._trk else trk
        raise NotImplementedError()

    def select(self, beads = None, cycles = None) -> Track:
        """
        Selects beads and cycles
        """
        return self.__getitem__((beads, cycles))

    def __setitem__(self, key: BEADKEY, val: BEADKEY) -> Track:
        if isinstance(key, (list, tuple)):
            return renamebeads(self._trk, *zip(key, val))
        return renamebeads(self._trk, (key, val))

@addto(Track)
def astracksdict(self, *beads:BEADKEY) -> TracksDict:
    """
    Converts this to a `TracksDict` object, with one bead per track.

    This can be used to work across beads in a track as one would accross
    tracks in a `TracksDict`.
    """
    if len(beads) == 1 and isinstance(beads[0], (tuple, list, set, frozenset)):
        beads = tuple(beads[0])
    if len(beads) == 0:
        beads = tuple(self.beadsonly.keys())
    return TracksDict({i: renamebeads(selectbeads(self, i), (i, 0)) for i in beads})

@addto(Track)
def __getitem__(self, value):
    if isinstance(value, (Task, Tasks)):
        value = (value,)

    if isinstance(value, range):
        value = set(value) & set(self.data.keys())

    if isinstance(value, (list, set, tuple, frozenset)):
        if all(isinstance(i, (Task, Tasks)) for i in value):
            return self.apply(*value)
        if '~' in value:
            return dropbeads(self, *(i for i in value if i != '~'))

    return selectbeads(self, value)

Track.cleaned = LazyProperty('cleaned')
addattributes(Track, protected = dict(cleaned = False))

Track.__doc__   += '* `op` a'+TrackOperations.__doc__[6:]
Track.__doc__   += '\n    * `pathinfo` p'+PathInfo.__doc__[6:]
Track.cycles    .args['copy'] = True
Track.cyclesonly.args['copy'] = True
Track.beads     .args['copy'] = True
Track.beadsonly .args['copy'] = True

__all__ = ['Track']
