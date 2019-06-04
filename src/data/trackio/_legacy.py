#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=arguments-differ
"Load trk tracks"
from    typing             import Optional, Iterator
from    itertools          import chain
from    pathlib            import Path

# pylint: disable=import-error,no-name-in-module
from    legacy             import readtrack, instrumenttype  as _legacyinstrumenttype
from    ._base             import TrackIO, PATHTYPE, PATHTYPES, globfiles
from    ._pickle           import PickleIO

class LegacyTrackIO(TrackIO):
    "checks and opens legacy track paths"
    PRIORITY = -1000
    TRKEXT   = '.trk'
    @classmethod
    def check(cls, path:PATHTYPES, **_) -> Optional[PATHTYPES]:
        "checks the existence of a path"
        return cls.checkpath(path, cls.TRKEXT)

    @staticmethod
    def open(path:PATHTYPE, **kwa) -> dict:
        "opens a track file"
        axis = kwa.pop('axis', 'Z')
        axis = getattr(axis, 'value', axis)[0]
        return readtrack(str(path), kwa.pop('notall', True), axis)

    @staticmethod
    def instrumenttype(path: str) -> str:
        "return the instrument type"
        return _legacyinstrumenttype(path)

    @classmethod
    def scan(cls, trkdirs) -> Iterator[Path]:
        "scan for track files"
        if not isinstance(trkdirs, (tuple, list, set, frozenset)):
            trkdirs = (trkdirs,)
        trkdirs = tuple(str(i) for i in trkdirs)
        if all(Path(i).is_dir() for i in trkdirs):
            for trk in (cls.TRKEXT, PickleIO.EXT):
                end = f'/**/*{trk}'
                lst = [i for i in chain.from_iterable(globfiles(str(k)+end) for k in trkdirs)]
                if len(lst):
                    yield from iter(lst)
                    break
            return

        trk = cls.TRKEXT
        fcn = lambda i: i if '*' in i or i.endswith(trk) else i+'/**/*'+trk
        yield from (i for i in chain.from_iterable(globfiles(fcn(str(k))) for k in trkdirs))
