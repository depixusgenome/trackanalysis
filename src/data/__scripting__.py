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
import sys
from typing                 import KeysView, Tuple, Iterator, List
from itertools              import product
from pathlib                import Path
import pickle
import re

from utils                  import initdefaults
from utils.decoration       import addto
from model                  import Level
from signalfilter           import PrecisionAlg, NonLinearFilter
from eventdetection.data    import Events

from .                      import Track as _Track, Beads, Cycles
from .trackio               import LegacyGRFilesIO, LegacyTrackIO

Tasks     = sys.modules['app.__scripting__'].Tasks     # pylint: disable=invalid-name
scriptapp = sys.modules['app.__scripting__'].scriptapp # pylint: disable=invalid-name

class Track(_Track):
    "Adding helper functions for simple calls"
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
    return Tasks.get(self.path, *args, beadsonly = beadsonly)

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

def _tasks(paths, upto):
    tasks = (Tasks.eventdetection, Tasks.peakselector)
    if isinstance(paths, (str, Path)) or len(paths) == 1:
        tasks = (Tasks.cleaning, Tasks.alignment)+tasks
    return (tasks if upto is None       else
            ()    if upto not in tasks  else
            tasks[:tasks.index(upto)+1])

@addto(_Track) # type: ignore
@property
def cleancycles(self):
    "returns cleaned cycles"
    return self.apply(*_tasks(self.path, Tasks.alignment))[...,...]

@addto(_Track) # type: ignore
@property
def measures(self):
    "returns cleaned cycles for phase 5 only"
    phase = scriptapp.control.getGlobal('config').phase.measure.get()
    return self.cleancycles.withphases(phase)

@addto(_Track) # type: ignore
@property
def events(self) -> Events:
    "returns events in phase 5 only"
    return self.apply(*_tasks(self.path, Tasks.eventdetection))

@addto(_Track) # type: ignore
@property
def peaks(self) -> Events:
    "returns peaks found"
    return self.apply(*_tasks(self.path, Tasks.peakselector))

def _fit(self, tpe, sequence, oligos, kwa) -> Events:
    "computes hairpin fits"
    if None not in (sequence, oligos):
        kwa['sequence'] = sequence
        kwa['oligos']   = oligos

    tasks = _tasks(self.path, None)+ (getattr(Tasks, tpe)(**kwa),) # type: tuple
    if len(tasks[-1].distances) == 0:
        raise IndexError('No distances found')
    return self.apply(*tasks)

@addto(_Track) # type: ignore
def fittohairpin(self, sequence = None, oligos = None, **kwa) -> Events:
    """
    Computes hairpin fits.

    Arguments are for creating the FitToHairpinTask.
    """
    return _fit(self, 'fittohairpin', sequence, oligos, kwa)

@addto(_Track) # type: ignore
def beadsbyhairpin(self, sequence, oligos, **kwa) -> Events:
    """
    Computes hairpin fits, sorted by best hairpin.

    Arguments are for creating the FitToHairpinTask.
    """
    return _fit(self, 'beadsbyhairpin', sequence, oligos, kwa)

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
        >>> match  = r".*test045_(\\w\\w\\w)_BNA.*" # select only test 045 and define the key
        >>> TRACKS = TracksDict(tracks, grs, match)
        >>> TRACKS['AAA'].cycles                  # access the track

    By default, the name of the track file is used as the key. Using the *match*
    requires defining a group which will be used as the key.
    """
    __SCAN_OPTS = ('cgrdir',)
    def __init__(self, tracks = None, grs = None, match = None, allaxes = False,
                 *tasks, **kwa):
        super().__init__()
        self.tasks = tasks
        self.update(tracks = tracks, grs = grs, match = match, allaxes = allaxes, **kwa)

    def __set(self, key, val, allaxes = False):
        if isinstance(val, (str, Path, tuple, list, set)):
            val = Track(path = val)

        elif isinstance(val, _Track) and not isinstance(val, Track):
            val = Track(**val.__getstate__())

        if len(self.tasks):
            val = val.apply(*self.tasks)
        super().__setitem__(key, val)

        if allaxes:
            cnf = val.__getstate__()
            for i in 'xy':
                cnf['axis'] = i
                super().__setitem__('X'+key, Track(**cnf))

        return val

    def __setitem__(self, key, val):
        return self.__set(key, val)

    def scan(self, tracks, grs = None, match = None, allaxes = False, **opts) -> KeysView[str]:
        "scans for trks and grs"
        if isinstance(match, str) or hasattr(match, 'match'):
            grp = True
            tmp = re.compile(match) if isinstance(match, str) else match
            fcn = lambda i: tmp.match(str(i[0]))
        else:
            grp = False
            fcn = lambda i: Path(str(i[0])).name if match is None else match

        if grs is None:
            itr = ((fcn((i,)), i) for i in LegacyTrackIO.scan(tracks))
        else:
            itr = ((fcn(i), i) for i in LegacyGRFilesIO.scan(tracks, grs, **opts)[0])

        info = dict((i.group(1), j) for i, j in itr if i) if grp else dict(itr)
        for i, j in info.items():
            self.__set(i, j, allaxes)
        return info.keys()

    def update(self, *args, tracks = None, grs = None, match = None, allaxes = False, **kwargs):
        "adds paths or tracks to self"
        scan    = {}
        for i in self.__SCAN_OPTS:
            if i in kwargs:
                scan[i] = kwargs.pop(i)

        info = {}
        info.update(*args, **kwargs)
        for i, j in info.items():
            self.__set(i, j, allaxes)

        if tracks is not None:
            assert sum(i is None for i in (tracks, grs)) in (0, 2)
            self.scan(tracks, grs, match, allaxes, **scan)

    def beads(self, *keys) -> List[int]:
        "returns the intersection of all beads in requested tracks"
        if len(keys) == 0:
            keys = tuple(self.keys())

        beads = set(self[keys[0]].beadsonly.keys())
        for key in keys[1:]:
            beads &= set(self[key].beadsonly.keys())

        return sorted(beads)

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

__all__ = ['Track', 'TracksDict', 'BeadsDict', 'Path']
