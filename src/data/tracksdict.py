#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Adds a dictionnaries to access tracks, experiments, ...
"""
from typing                 import KeysView, List, Dict
from pathlib                import Path
import re

from .track                 import Track
from .trackio               import LegacyGRFilesIO, LegacyTrackIO

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
                 **kwa):
        super().__init__()
        self.update(tracks = tracks, grs = grs, match = match, allaxes = allaxes, **kwa)

    @staticmethod
    def _newtrack(**kwa):
        return Track(**kwa)

    def _set(self, key, val, allaxes = False):
        if isinstance(val, (str, Path, tuple, list, set)):
            state = dict(path = val)
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
