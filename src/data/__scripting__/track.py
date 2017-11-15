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
from itertools              import product
from pathlib                import Path
from datetime               import datetime

from utils.decoration       import addto, addproperty
from signalfilter           import PrecisionAlg
from app.__scripting__      import Tasks, scriptapp

from ..                      import Track as _Track

class Track(_Track):
    """
    * `pathinfo` provides information on the path itself:

        * `paths`: a tuple of paths
        * `trackpath`: the main path, i.e. not the grs
        * `size` (*megabytes*) is the size in bytes (megabytes) of *trackpath*
        * `stat`: stats on the *trackpath*
        * `modification`: the date oflast modification. This is basically the
        time of experiment.
        * `creation`: the creation date. **DISCARD** when using PicoTwist tracks.
    """
    __doc__ = _Track.__doc__ + __doc__
    cleaned = False
    def __init__(self, path = None, **kwa):
        cnf = scriptapp.control.getGlobal('css').last.path.trk
        if path in (Ellipsis, 'prev', ''):
            path = cnf.get()

        if path is None:
            path = scriptapp.trkdlg.open()
            if path is None:
                path = ''

        if isinstance(path, (tuple, str)):
            cnf.set(path)
            scriptapp.control.writeuserconfig()
        super().__init__(path = path, **kwa)
        self.cleaned = kwa.get('cleaned', type(self).cleaned)

_Track.__doc__ = Track.__doc__

@addproperty(_Track, 'pathinfo')
class PathInfo:
    "Provides access to path information"
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

@addto(_Track)
def grfiles(self):
    "access to gr files"
    paths = scriptapp.grdlg.open()
    if paths is None or len(paths) == 0:
        return
    old = self.path
    self.__init__(path = ((old,) if isinstance(old, str) else old)+paths)

@addto(_Track)
def rawprecision(self, ibead):
    "the raw precision for a given bead"
    if isinstance(ibead, (tuple, list)):
        ibead = next(i for i in ibead if isinstance(i, int))
    return PrecisionAlg.rawprecision(self, ibead)

@addto(_Track)
def tasklist(self, *args, beadsonly = True):
    "creates a tasklist"
    return Tasks.tasklist(self.path, *args, beadsonly = beadsonly)

@addto(_Track)
def processors(self, *args, copy = True, beadsonly = True):
    "returns an iterator over the result of provided tasks"
    procs = Tasks.processors(self.path, *args, beadsonly = beadsonly)
    procs.data.setCacheDefault(0, self)
    procs.copy = copy
    return procs

@addto(_Track)
def apply(self, *args, copy = True, beadsonly = True):
    "returns an iterator over the result of provided tasks"
    return next(iter(self.processors(*args, beadsonly = beadsonly).run(copy = copy)))

@addto(_Track) # type: ignore
@property
def cleancycles(self):
    "returns cleaned cycles"
    return self.apply(*Tasks.defaulttasklist(self.path, Tasks.alignment, self.cleaned))[...,...]

@addto(_Track) # type: ignore
@property
def measures(self):
    "returns cleaned cycles for phase 5 only"
    phase = scriptapp.control.getGlobal('config').phase.measure.get()
    return self.cleancycles.withphases(phase)

def _addprop(name):
    fcn = getattr(_Track, name).fget
    setattr(Track, name, property(lambda self: fcn(self).withcopy(),
                                  doc = getattr(Track, name).__doc__))

for tname in product(('beads', 'cycles'), ('only', '')):
    _addprop(''.join(tname))

__all__ = ['Track']
