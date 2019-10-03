#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=arguments-differ
"Load trk tracks"
from    typing             import Optional, Iterator, Dict, Any
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
        cycles = kwa.pop('cycles', None)
        start  = 0#cycles.start if cycles else -1
        stop   = cycles.stop+5 if cycles else -1
        axis   = kwa.pop('axis', 'Z')
        axis   = getattr(axis, 'value', axis)[0]
        return readtrack(str(path), kwa.pop('notall', True), axis, start, stop)

    @staticmethod
    def instrumentinfo(path: str) -> Dict[str, Any]:
        "return the instrument type"
        return {'type': _legacyinstrumenttype(path), 'dimension': 'µm', 'name': None}

    @classmethod
    def scan(cls, trkdirs) -> Iterator[Path]:
        "scan for track files"
        if not isinstance(trkdirs, (tuple, list, set, frozenset)):
            trkdirs = (trkdirs,)
        trkdirs = tuple(str(i) for i in trkdirs)
        if all(Path(i).is_dir() for i in trkdirs):
            for trk in (cls.TRKEXT, PickleIO.EXT):
                end = f'/**/*{trk}'
                lst = list(chain.from_iterable(globfiles(str(k)+end) for k in trkdirs))
                if len(lst):
                    yield from iter(lst)
                    break
            return

        trk = cls.TRKEXT
        fcn = lambda i: i if '*' in i or i.endswith(trk) else i+'/**/*'+trk
        yield from (i for i in chain.from_iterable(globfiles(fcn(str(k))) for k in trkdirs))
