#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Adds a dictionnaries to access tracks, experiments, ...
"""
from   typing               import Tuple, Iterator, List, cast
import pickle

from   utils                import initdefaults
from   utils.decoration     import addto

from   model                import Level, Task
from   model.__scripting__  import Tasks

from   .track               import Track
from   ..trackio            import savetrack, PATHTYPE, Handler
from   ..tracksdict         import TracksDict as _TracksDict

@addto(Handler)
def __call__(self, track = None, beadsonly = False, __old__ = Handler.__call__) -> Track:
    if track is None:
        track = Track()
    return __old__(self, track, beadsonly)

class TracksDict(_TracksDict):
    """
    # Saving

    It's possible to save the tracks to a '.pk' format as follows:

        >>> tracks.save("/path/to/my/saved/tracks")

    The tracks are saved as "/path/to/my/saved/tracks/key.pk" files.
    Thus, loading them is as simple as:

        >>> TRACKS = TracksDict("/path/to/my/saved/tracks/*.pk")
    """
    __doc__     = _TracksDict.__doc__ + __doc__
    _TRACK_TYPE = Track
    def __init__(self,          # pylint: disable=too-many-arguments
                 tracks  = None,
                 grs     = None,
                 match   = None,
                 allaxes = False,
                 tasks   = None,
                 cleaned = None,
                 **kwa):
        super().__init__(tracks, grs, match, allaxes, **kwa)
        if cleaned is not None:
            self.cleaned = cleaned
        self.tasks   = tasks

    def __getitem__(self, key):
        if isinstance(key, list):
            return super().__getitem__(key)

        if isinstance(key, (Task, Tasks)):
            return self.apply(key)

        if isinstance(key, tuple) and all(isinstance(i, (Task, Tasks)) for i in key):
            return self.apply(*key)

        trk = super().__getitem__(key)
        return trk.apply(*self.tasks) if self.tasks else trk

    def apply(self, *tasks) -> 'TracksDict':
        "returns a new tracksdict with default tasks"
        other = type(self)(tasks = tasks)
        other.update(self)
        return other

    def save(self, path: PATHTYPE) -> 'TracksDict':
        "saves the data to a directory"
        if self.tasks:
            raise NotImplementedError("don't know how to save that")
        return savetrack(path, self)

    @property
    def cleaned(self):
        "wether all tracks are cleaned"
        return all(i.cleaned for i in self.values())

    @cleaned.setter
    def cleaned(self, value):
        """
        Sets tracks to cleaned.

        If provided with a string or a list, the corresponding tracks are defined
        as cleaned, the others as dirty.
        """
        if isinstance(value, (str, list)):
            self.cleaned        = False
            self[value].cleaned = True

        else:
            for i in self.values():
                i.cleaned = value

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
            vals = tmp if vals is None else cast(frozenset, vals) & tmp
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
