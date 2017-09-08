#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Adds a dictionnaries to access tracks, experiments, ...
"""
from typing                 import KeysView, Tuple, Iterator, List, Type
from pathlib                import Path
import sys
import pickle
import re

from utils                  import initdefaults
from model                  import Level, Task

from ..                     import Track as _Track
from .track                 import Track
from ..trackio              import LegacyGRFilesIO, LegacyTrackIO

Tasks: Type = sys.modules['model.__scripting__'].Tasks

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
    def __init__(self,          # pylint: disable=too-many-arguments
                 tracks  = None,
                 grs     = None,
                 match   = None,
                 allaxes = False,
                 tasks   = None,
                 **kwa):
        super().__init__()
        self.tasks  = tasks
        self.update(tracks = tracks, grs = grs, match = match, allaxes = allaxes, **kwa)

    def __set(self, key, val, allaxes = False):
        if isinstance(val, (str, Path, tuple, list, set)):
            val = Track(path = val)

        elif isinstance(val, _Track) and not isinstance(val, Track):
            val = Track(**val.__getstate__())

        super().__setitem__(key, val)

        if allaxes:
            cnf = val.__getstate__()
            for i in 'xy':
                cnf['axis'] = i
                super().__setitem__('X'+key, Track(**cnf))

        return val

    def __getitem__(self, key):
        if isinstance(key, (Task, Tasks)):
            return self.apply(key)
        if isinstance(key, tuple) and all(isinstance(i, (Task, Tasks)) for i in key):
            return self.apply(*key)

        trk = super().__getitem__(key)
        return trk.apply(*self.tasks) if self.tasks else trk

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

    def update(self, *args,
               tracks  = None,
               grs     = None,
               match   = None,
               allaxes = False,
               **kwargs):
        "adds paths or tracks to self"
        scan    = {}
        for i in self.__SCAN_OPTS:
            if i in kwargs:
                scan[i] = kwargs.pop(i)

        info = {} # type: ignore
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

    def apply(self, *tasks) -> 'TracksDict':
        "returns a new tracksdict with default tasks"
        other = type(self)(tasks = tasks)
        other.update(self)
        return other

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

__all__ = ['TracksDict', 'BeadsDict', 'ExperimentList']
