#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=arguments-differ
"Loading and save tracks in  .pk format"
import  sys
from    importlib          import import_module
from    typing             import (
    Any, Union, Optional, Dict, cast, overload, TYPE_CHECKING
)
from    concurrent.futures import ThreadPoolExecutor
from    copy               import copy as shallowcopy
from    pathlib            import Path
import  pickle
from    ._base             import TrackIO, PATHTYPE, PATHTYPES, DictType
if TYPE_CHECKING:
    from    ._base         import Track

class PickleIO(TrackIO):
    "checks and opens pickled paths"
    EXT = '.pk'
    @classmethod
    def check(cls, path:PATHTYPES, **_) -> Optional[PATHTYPES]:
        "checks the existence of a path"
        return cls.checkpath(path, cls.EXT)

    @staticmethod
    def open(path:PATHTYPE, **_) -> Dict[Union[str, int], Any]:
        "opens a track file"
        out   = None
        names = {
            "cleaning.processor": None,
            "cleaning.beadsubtraction": None,
            "peakfinding.processor.peakfiltering": "peakfinding.processor.singlestrand",
            "taskmodel":                           "model.task",
            "taskmodel.level":                     "model.level"
        }
        try:
            for i, j in names.items():
                mdl = import_module(i)
                if j:
                    sys.modules[j] = mdl

            setattr(
                import_module("cleaning.beadsubtraction"),
                "BeadSubtractionTask",
                getattr(import_module("cleaning.processor"), "BeadSubtractionTask")
            )
            try:
                with open(path, 'rb') as stream:
                    out = pickle.load(stream)
            except ModuleNotFoundError:
                names["taskmodel.__scripting__"] = "model.__scripting__"
                for i, j in names.items():
                    mdl = import_module(i)
                    if j:
                        sys.modules[j] = mdl


                with open(path, 'rb') as stream:
                    out = pickle.load(stream)

            for i in ('secondaries', 'data', 'fov'):
                if out.get(i, None) is None:
                    out.pop(i, None)

        finally:
            if hasattr(import_module("cleaning.beadsubtraction"), "BeadSubtractionTask"):
                delattr(import_module("cleaning.beadsubtraction"), "BeadSubtractionTask")
            for j in names.values():
                if j:
                    sys.modules.pop(j, None)
        return out

    @classmethod
    def save(cls, path: PATHTYPE, track: Union[dict, 'Track']):
        "saves a track file"
        from ._handler import Handler
        info = track if isinstance(track, dict) else Handler.todict(track)
        with open(path, 'wb') as stream:
            return pickle.dump(info, stream)

    @classmethod
    def instrumentinfo(cls, path: str) -> Dict[str, Any]:
        "return the instrument type"
        return cls.open(path).get('instrument', {'type': 'picotwist', 'dimension': 'µm'})


N_SAVE_THREADS = 4

def _savetrack(args):
    if not isinstance(args[2], dict):
        try:
            PickleIO.save(args[1], args[2])
        except Exception as exc:
            raise IOError(f"Could not save {args[2].path} [{args[2].key}]") from exc
    else:
        PickleIO.save(args[1], args[2])
    new = type(args[2]).__new__(type(args[2])) # type: ignore
    new.__dict__.update(shallowcopy(args[2].__dict__))
    setattr(new, '_path', args[1])
    return args[0], new

@overload
def savetrack(path: PATHTYPE, track: 'Track') -> 'Track':
    "saves a track"

@overload
def savetrack(path  : PATHTYPE, track : DictType) -> DictType: # type: ignore
    "saves a tracksdict"

def savetrack(path  : PATHTYPE, track : Union['Track', Dict[str,'Track']]
             ) -> Union['Track', Dict[str,'Track']]:
    "Saves a track"
    if isinstance(track, (str, Path)):
        path, track = track, path

    if isinstance(track, dict):
        root = Path(path)
        root.mkdir(parents=True, exist_ok=True)

        args = [(key, (root/key).with_suffix(PickleIO.EXT), trk)
                for key, trk in cast(dict, track).items()]
        new  = shallowcopy(track)
        with ThreadPoolExecutor(N_SAVE_THREADS) as pool:
            new.update({i: j for i, j in pool.map(_savetrack, args)})
        return new

    return _savetrack((None, path, track))[1]
