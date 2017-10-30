#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Adds a dictionnaries to access tracks, experiments, ...
"""
from typing             import (KeysView, List, Dict, Any, # pylint: disable=unused-import
                                Iterator, Tuple, TypeVar, Union, Set, Optional, cast)
from pathlib            import Path
from concurrent.futures import ThreadPoolExecutor
from copy               import copy as shallowcopy
import re

from .views   import isellipsis, BEADKEY
from .track   import Track
from .trackio import LegacyGRFilesIO, LegacyTrackIO, PATHTYPES

TDictType = TypeVar('TDictType', bound = 'TracksDict')
TrackType = TypeVar('TrackType', bound = 'Track')
class TracksDict(dict):
    """
    Dictionnary of tracks

    ### Initialisation

    It can be initialized using list of directories

        >>> tracks = "/path/to/my/trackfiles/**/with/recursive/search/*.trk"
        >>> grs    = ("/more/than/a/single/path/**", "/is/possible/**")
        >>> match  = r".*test045_(\\w\\w\\w)_BNA.*" # select only test 045 and define the key
        >>> TRACKS = TracksDict(tracks, grs, match)
        >>> TRACKS['AAA'].cycles                  # access the track

    By default, the name of the track file is used as the key. Using the *match*
    requires defining a group which will be used as the key.

    ### Shortcuts

    *TracksDict.beads* returns the beads in common to all tracks in the *TracksDict*.

    ### Slicing

    Providing a list of keys as argument creates a new TracksDict containing
    only those keys. The same *Track* objects are used.

        >>> dico = TracksDict()
        >>> dico.update(A = "a.trk", B = "b.trk", C = "c.trk")
        >>> assert dico['A'].path == "a.trk"

        >>> fraction = dico[['A']]
        >>> assert isinstance(fraction, TracksDict)
        >>> assert set(fraction.keys()) == {'A'}
        >>> assert fraction['A'] is dico['A']

    If within that list, the key "~" appears, then all but the provided
    keys are used:

        >>> assert set(dico['~A'].keys()) == {'B', 'C'}
        >>> assert set(dico[['~', 'B', 'C'].keys()) == {'A'}

    Should a key  with "~", then that keye
    only those keys.
    """
    _SCAN_OPTS  = ('cgrdir',)
    _NTHREADS   = 4
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

    def __getitem__(self: TDictType, # pylint: disable=function-redefined
                    key: Union[List,Any]
                   ) -> Union[TDictType, TrackType]:
        if isellipsis(key):
            return shallowcopy(self)

        if isinstance(key, str) and len(key) and key[0] == '~' and key not in self:
            key = ['~', key[1:]]

        if isinstance(key, list):
            other = shallowcopy(self)
            bad   = set(key) - {'~'} if '~' in key else set(other)-set(key)
            for i in bad:
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
        for i in self._SCAN_OPTS:
            if i in kwargs:
                scan[i] = kwargs.pop(i)

        info = {} # type: ignore
        info.update(*args, **kwargs)
        for i, j in info.items():
            self._set(i, j, allaxes)

        if tracks is not None:
            assert sum(i is None for i in (tracks, grs)) in (0, 1, 2)
            self.scan(tracks, grs, match, allaxes, **scan)

    def availablebeads(self, *keys) -> List[BEADKEY]:
        "returns the intersection of all beads in requested tracks (all by default)"
        if len(keys) == 0:
            keys = tuple(self.keys())

        fcn   = lambda key: set(cast(Track, self[key]).beadsonly.keys())
        beads = None # type: Optional[Set[BEADKEY]]
        with ThreadPoolExecutor(self._NTHREADS) as pool:
            for cur in pool.map(fcn, keys):
                beads = cur if beads is None else (cur & beads)

        return sorted(beads)

    def availablekeys(self, *abeads) -> List:
        "returns the intersection of all beads in requested tracks (all by default)"
        if len(abeads) == 0:
            return sorted(super().keys())

        beads = set(abeads)
        fcn   = lambda key: (key, len(beads - set(cast(Track, self[key]).beadsonly.keys())))
        keys  = [] # type: list
        with ThreadPoolExecutor(self._NTHREADS) as pool:
            for key, cur in pool.map(fcn, tuple(super().keys())):
                if cur == 0:
                    keys.append(key)

        return sorted(keys)
