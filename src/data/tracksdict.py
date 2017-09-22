#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Adds a dictionnaries to access tracks, experiments, ...
"""
from typing                 import KeysView, List, Dict, Any, Iterator, Tuple, cast
from pathlib                import Path
from copy                   import copy as shallowcopy
import re

from .views                 import isellipsis
from .track                 import Track
from .trackio               import LegacyGRFilesIO, LegacyTrackIO, PATHTYPES

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
    _TRACK_TYPE = Track
    def __init__(self,          # pylint: disable=too-many-arguments
                 tracks  = None,
                 grs     = None,
                 match   = None,
                 allaxes = False,
                 **kwa):
        super().__init__()
        self.update(tracks = tracks, grs = grs, match = match, allaxes = allaxes, **kwa)

    @classmethod
    def _newtrack(cls, **kwa):
        return cls._TRACK_TYPE(**kwa)

    def _set(self, key, val, allaxes = False):
        # pylint: disable=unidiomatic-typecheck
        if type(val) is self._TRACK_TYPE and not allaxes:
            super().__setitem__(key, val)
            return

        if isinstance(val, (tuple, list, set)) and len(val) == 1:
            val = str(next(iter(val)))

        if isinstance(val, (tuple, list, set)):
            state = dict(path = [str(i) for i in val]) # type: Dict[str, Any]
        elif isinstance(val, (str, Path)):
            state = dict(path = str(val))
        elif isinstance(val, dict):
            state = val
        elif isinstance(val, Track):
            state = val.__getstate__()
        else:
            raise NotImplementedError()

        for i in 'XYZ' if allaxes else 'Z':
            state['axis'] = i
            state['key']  = f'{i if i != "Z" else ""}{key}'
            super().__setitem__(state['key'], self._newtrack(**state))

        return val

    def __setitem__(self, key, val):
        return self._set(key, val)

    def __getitem__(self, key):
        if isellipsis(key):
            return shallowcopy(self)

        if isinstance(key, list):
            other = shallowcopy(self)
            for i in set(other)-set(key):
                other.pop(i)
            return other
        return super().__getitem__(key)

    @staticmethod
    def scangrs(grdirs, **opts) -> Dict[str, Path]:
        "scan for gr files"
        return LegacyGRFilesIO.scangrs(grdirs, **opts)

    @staticmethod
    def scantrk(trkdirs) -> Dict[str, Path]:
        "scan for track files"
        return LegacyGRFilesIO.scantrk(trkdirs)

    def scan(self, tracks, grs = None, match = None, allaxes = False, **opts) -> KeysView[str]:
        "scans for trks and grs"
        if isinstance(match, str) or hasattr(match, 'match'):
            grp = True
            tmp = re.compile(match) if isinstance(match, str) else match
            fcn = lambda i: tmp.match(str(i if isinstance(i, (str, Path)) else i[0]))
        else:
            grp = False
            fcn = lambda i: (Path(str(i if isinstance(i, (str, Path)) else i[0])).name
                             if match is None else match)

        if not grs:
            itr = cast(Iterator[Tuple[Any, PATHTYPES]],
                       ((fcn((i,)), i) for i in LegacyTrackIO.scan(tracks)))
        else:
            itr = ((fcn(i), i) for i in LegacyGRFilesIO.scan(tracks, grs, **opts)[0])

        info = dict((i.group(1), j) for i, j in itr if i) if grp else dict(itr)
        for i, j in info.items():
            self._set(i, j, allaxes)
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
            self._set(i, j, allaxes)

        if tracks is not None:
            assert sum(i is None for i in (tracks, grs)) in (0, 1, 2)
            self.scan(tracks, grs, match, allaxes, **scan)

    def beads(self, *keys) -> List[int]:
        "returns the intersection of all beads in requested tracks"
        if len(keys) == 0:
            keys = tuple(self.keys())

        beads = set(self[keys[0]].beadsonly.keys())
        for key in keys[1:]:
            beads &= set(self[key].beadsonly.keys())

        return sorted(beads)
