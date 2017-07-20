#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Monkey patches the Track class.

We add some methods and change the default behaviour:

    * Track:

        * *__init__* takes *path* as it's first positional argument
        * an *events* property is added
        * a *rawprecision* method is added

    * Beads, Cycles:

        * can filter their output using *withfilter*

    * Beads, Cycles, Events:

        * *withcopy(True)* is called in the *__init__* by default
        * a *rawprecision* method is added
        * *with...* methods return an updated copy
"""
from typing                 import Dict, KeysView, Tuple, Iterator, List
from itertools              import product
from pathlib                import Path
import pickle
import re

from utils                  import initdefaults
from model                  import Level
from data                   import Track as _Track, Beads, Cycles
from data.trackio           import LegacyGRFilesIO
from signalfilter           import PrecisionAlg, NonLinearFilter
from eventdetection.data    import Events

from .scriptapp             import scriptapp, Tasks

class Track(_Track):
    "Adding helper functions for simple calls"
    def __init__(self, path = None, **kwa):
        cnf = scriptapp.control.getGlobal('config').last.path.trk
        if path in (Ellipsis, 'prev', ''):
            path = cnf.get()

        if path is None:
            path = scriptapp.trkdlg.open()
            if path is None:
                path = ''

        if isinstance(path, (tuple, str)):
            cnf.set(path)
            scriptapp.control.writeconfig()
        super().__init__(path = path, **kwa)

def _totrack(fcn):
    setattr(_Track, getattr(fcn, 'fget', fcn).__name__, fcn)

@_totrack
def grfiles(self):
    "access to gr files"
    paths = scriptapp.grdlg.open()
    if paths is None or len(paths) == 0:
        return
    old = self.path
    self.__init__(path = ((old,) if isinstance(old, str) else old)+paths)

@_totrack
def rawprecision(self, ibead):
    "the raw precision for a given bead"
    if isinstance(ibead, (tuple, list)):
        ibead = next(i for i in ibead if isinstance(i, int))
    return PrecisionAlg.rawprecision(self, ibead)

@_totrack
def tasklist(self, *args, beadsonly = True):
    "creates a tasklist"
    return Tasks.get(self.path, *args, beadsonly = beadsonly)

@_totrack
def processors(self, *args, copy = True, beadsonly = True):
    "returns an iterator over the result of provided tasks"
    procs = Tasks.processors(self.path, *args, beadsonly = beadsonly)
    procs.data.setCacheDefault(0, self)
    procs.copy = copy
    return procs

@_totrack
def apply(self, *args, copy = True, beadsonly = True):
    "returns an iterator over the result of provided tasks"
    return next(iter(self.processors(*args, beadsonly = beadsonly).run(copy = copy)))

@_totrack # type: ignore
@property
def measures(self):
    "returns cycles for phase 5 only"
    phase = scriptapp.control.getGlobal('config').phase.measure.get()
    return self.cycles.withphases(phase)

@_totrack # type: ignore
@property
def events(self) -> Events:
    "returns events in phase 5 only"
    phase = scriptapp.control.getGlobal('config').phase.measure.get()
    return Events(track   = self,  data = self.beadsonly,
                  first   = phase, last = phase,
                  parents = (self.path,))

@_totrack # type: ignore
@property
def peaks(self) -> Events:
    "returns peaks found"
    tasks = (Tasks.eventdetection, Tasks.peakselector) # type: tuple
    if not (isinstance(self.path, (str, Path)) or len(self.path) == 1):
        tasks = (Tasks.alignment,) + tasks
    return self.apply(*tasks)

def _addprop(name):
    fcn = getattr(_Track, name).fget
    setattr(Track, name, property(lambda self: fcn(self).withcopy()))

for tname in product(('beads', 'cycles'), ('only', '')):
    _addprop(''.join(tname))

def _withfilter(self, tpe = NonLinearFilter, **kwa):
    "applies the filter to the data"
    filt = tpe(**kwa)
    fcn  = lambda info: (info[0],
                         filt(info[1], precision = self.track.rawprecision(info[0])))
    return self.withaction(fcn)

for _cls in (Beads, Cycles, Events):
    _cls.withfilter = _withfilter

class TracksDict(dict):
    """
    Dictionnary of tracks

    It can be initialized using list of directories

        >>> tracks = "/path/to/my/trackfiles/**/with/recursive/search/*.trk"
        >>> grs    = ("/more/than/a/single/path/**", "/is/possible/**")
        >>> match  = r".*test045_(?\\w\\w\\w)_BNA.*" # select only test 045 and define the key
        >>> TRACKS = TracksDict(tracks, grs, match)
        >>> TRACKS['AAA'].cycles                  # access the track

    By default, the name of the track file is used as the key. Using the *match*
    requires defining a group which will be used as the key.
    """
    __SCAN_OPTS = ('cgrdir',)
    def __init__(self, tracks = None, grs = None, match = None, *tasks, **kwa):
        super().__init__()
        self.paths : Dict[str, Tuple[str,...]] = {}
        self.tasks = tasks
        self.update(tracks = tracks, grs = grs, match = match, **kwa)

    def __setitem__(self, key, val):
        if isinstance(val, (str, Path, tuple, list, set)):
            self.paths[key] = val
            return val

        if isinstance(val, _Track) and not isinstance(val, Track):
            val = _Track(**val.__dict__)

        if len(self.tasks):
            val = val.apply(*self.tasks)
        super().__setitem__(key, val)
        return val

    def scan(self, tracks, grs, match = None, **opts) -> KeysView[str]:
        "scans for trks and grs"
        if isinstance(match, str) or hasattr(match, 'match'):
            grp = True
            tmp = re.compile(match) if isinstance(match, str) else match
            fcn = lambda i: tmp.match(str(i[0]))
        else:
            grp = False
            fcn = lambda i: Path(str(i[0])).name if match is None else match

        itr  = ((fcn(i), i) for i in LegacyGRFilesIO.scan(tracks, grs, **opts)[0])
        info = dict((i.group(1), j) for i, j in itr if i) if grp else dict(itr)
        self.paths.update(info)
        return info.keys()

    def update(self, *args, tracks = None, grs = None, match = None, **kwargs):
        "adds paths or tracks to self"
        scan = {}
        for i in self.__SCAN_OPTS:
            if i in kwargs:
                scan[i] = kwargs.pop(i)

        info = {}
        info.update(*args, **kwargs)
        for i, j in info.items():
            self.__setitem__(i, j)

        if tracks is not None:
            assert sum(i is None for i in (tracks, grs)) in (0, 2)
            self.scan(tracks, grs, match, **scan)

    def __missing__(self, olig):
        return self.__setitem__(olig, Track(path = self.paths.get(olig, olig)))

class ExperimentList(dict):
    "Provides access to keys belonging to a single experiment"
    tracks : dict                 = TracksDict()
    keysize: int                  = 3
    keylist: List[Tuple[str,...]] = []
    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        super().__init__()

    def __missing__(self, keys):
        keys = self.convert(keys)
        vals = None
        for key in keys:
            tmp  = frozenset(self.tracks[key].beadsonly.keys())
            vals = tmp if vals is None else vals & tmp
        self.__setitem__(keys, vals)
        return vals

    def convert(self, keys):
        "converts keys to a list of keys"
        if isinstance(keys, str):
            if self.keysize is not None and len(keys) > self.keysize:
                keys = tuple(keys[i:i+self.keysize] for i in range(len(keys)-self.keysize+1))
            else:
                keys = next(i for i in self.keylist if keys in i)
        return keys

    def word(self, keys):
        "converts keys to a word"
        keys = self.convert(keys)
        return keys[0]+''.join(i[-1] for i in keys[1:])

    def allkeys(self, oligo):
        "returns all oligos used by a key"
        return (next((list(i) for i in self.keylist if oligo in i), [oligo])
                if isinstance(oligo, str) else
                list(oligo))

    def available(self, *oligos):
        "returns available oligos"
        beads = set(self.tracks[oligos[0]].beadsonly.keys())
        for oligo in oligos[1:]:
            beads &= set(self.tracks[oligo].beadsonly.keys())
        return list(beads)

class BeadsDict(dict):
    """
    A dictionnary of potentially transformed bead data.

    Keys are combinations of a track key and a bead number.
    """
    def __init__(self, tracks, *tasks):
        super().__init__(self)
        self.tracks = tracks
        self.tasks  = tasks

    def __missing__(self, key):
        trk   = self.tracks[key[0]]
        if len(key) == 2 and len(self.tasks) == 0:
            return trk.beads[key[1]]

        tasks = trk.tasklist(*(self.tasks if len(key) == 2 else key[2:]))
        if len(key) > 2:
            key = key[0], key[1], pickle.dumps(tasks[1:])

        if key in self:
            return self[key]

        itm = trk.apply(*tasks[1:])
        if itm.level in (Level.cycle, Level.event):
            val = list(itm[key[1],...].values())
        else:
            val = itm[key[1]]
            if isinstance(val, Iterator):
                val = tuple(val)

        self.__setitem__(key, val)
        return val


__all__ = ['Track', 'TracksDict', 'BeadsDict']
