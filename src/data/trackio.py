#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Loading and save tracks"
from    typing      import (Sequence, Callable, # pylint: disable=unused-import
                            Any, Union, Tuple, Optional, TYPE_CHECKING)
from    inspect     import signature
import  pickle
import  re
from    functools   import wraps
from    pathlib     import Path
import  numpy       as     np

from    legacy      import readtrack, readgr # pylint: disable=import-error,no-name-in-module
if TYPE_CHECKING:
    from data import Track  # pylint: disable=unused-import

PATHTYPE  = Union[str, Path]
PATHTYPES = Union[PATHTYPE,Tuple[PATHTYPE,PATHTYPE]]

def _checktype(fcn):
    sig = signature(fcn)
    tpe = tuple(sig.parameters.values())[-1].annotation
    if tpe is sig.empty:
        tpe = Any
    elif tpe == Tuple[PATHTYPE,PATHTYPE]:
        tpe = tuple
    else:
        tpe = getattr(tpe, '__union_params__', tpe)
        if str(getattr(tpe, '__origin__', tpe)) == 'typing.Union':
            tpe = getattr(tpe, '__args__', tpe)

    @wraps(fcn)
    def _wrapper(*args):
        if tpe is Any or isinstance(args[-1], tpe):
            return fcn(*args)
        return None
    return _wrapper

def _fromdict(fcn) -> Callable[..., 'Track']:
    @wraps(fcn)
    def _wrapper(*args):
        kwargs = fcn(*args[:-1]+(args[-1].path,))

        if kwargs is None:
            args[-1].data = dict()
        else:
            for name in {'phases', 'framerate'} & set(kwargs):
                setattr(args[-1], name, kwargs.pop(name))

            args[-1].data = dict(ite for ite in kwargs.items()
                                 if isinstance(ite[1], np.ndarray))
        return args[-1]
    return _wrapper

class _TrackIO:
    @staticmethod
    def check(path):
        u"checks the existence of a path"
        raise NotImplementedError()

    @staticmethod
    def open(path):
        u"opens a track file"
        raise NotImplementedError()

class PickleIO(_TrackIO):
    u"checks and opens pickled paths"
    @staticmethod
    @_checktype
    def check(path:PATHTYPE) -> Optional[PATHTYPE]:
        u"checks the existence of a path"
        return path if Path(path).suffix == ".pk" else None

    @staticmethod
    @_fromdict
    def open(path:PATHTYPE) -> dict:
        u"opens a track file"
        with open(str(path), 'rb') as stream:
            return pickle.load(stream)

class LegacyTrackIO(_TrackIO):
    u"checks and opens legacy track paths"
    @staticmethod
    @_checktype
    def check(path:PATHTYPE) -> Optional[PATHTYPE]:
        u"checks the existence of a path"
        return path if Path(path).suffix == ".trk" else None

    @staticmethod
    @_fromdict
    def open(path:PATHTYPE) -> dict:
        u"opens a track file"
        return readtrack(str(path))

class LegacyGRFilesIO(_TrackIO):
    u"checks and opens legacy GR files"
    __TITLE   = re.compile(r"\\stack{{Bead (?P<id>\d+) Z.*?phase\(s\)"
                           +r" \[(?P<phases>.*?)\]}}")
    __GRTITLE = re.compile(r"Bead Cycle (?P<id>\d+) p.*")
    @classmethod
    @_checktype
    def check(cls, paths:Tuple[PATHTYPE,PATHTYPE] # type: ignore
             ) -> Optional[Tuple[PATHTYPE,PATHTYPE]]:
        u"checks the existence of paths"
        if all(Path(i).suffix != '.trk' for i in paths):
            return None

        if Path(paths[0]).is_dir():
            paths = paths[1], paths[0]

        if not Path(paths[1]).is_dir():
            raise IOError("[LegacyGRFilesIO] Missing directory in:\n- {}\n- {}"
                          .format(*paths))

        if all(i.suffix != '.gr' for i in Path(paths[1]).iterdir()):
            raise IOError("[LegacyGRFilesIO] No .gr files in directory\n- {}"
                          .format(paths[1]))
        fname = str(paths[0])
        if '*' in fname:
            return cls.__findtrk(fname, paths[1])

        elif not Path(paths[0]).exists():
            raise IOError("Could not find path: " + str(paths[0]))

        return paths

    @classmethod
    @_fromdict
    def open(cls, paths:Tuple[PATHTYPE,PATHTYPE]) -> dict: # type: ignore
        u"opens the directory"
        output = readtrack(str(paths[0]))
        remove = set(i for i in output if isinstance(i, int))

        for grpath in Path(paths[1]).iterdir():
            if grpath.suffix != ".gr":
                continue

            remove.discard(cls.__update(str(grpath), output))

        for key in remove:
            output.pop(key)
        return output

    @staticmethod
    def __findtrk(fname:str, grs:PATHTYPE) -> Tuple[PATHTYPE,PATHTYPE]:
        cgr  = next((i for i in Path(grs).iterdir() if i.suffix == '.cgr'),
                    None)
        if cgr is None:
            raise IOError("[LegacyGRFilesIO] No .cgr files in directory\n- {}"
                          .format(grs))

        pot    = cgr.with_suffix('.trk').name
        ind    = fname.find('*')
        root   = Path(fname[:ind])
        if root != Path(fname).parent:
            glob   = root.name+fname[ind:]
            parent = Path(str(root.parent))
        else:
            glob   = fname[ind:]
            parent = root
        trk    = next((i for i in parent.glob(glob) if i.name == pot), None)
        if trk is None:
            raise IOError("[LegacyGRFilesIO] Could not find {} in {}"
                          .format(pot, fname))
        return trk, grs

    @classmethod
    def __update(cls, path:str, output:dict) -> int:
        u"verifies one gr"
        grdict = readgr(path)
        tit    = cls.__TITLE.match(grdict['title'])

        if tit is None:
            raise IOError("Could not match title in " + path)

        beadid = int(tit.group("id"))
        if beadid not in output:
            raise IOError("Could not find bead "+str(beadid)+" in " + path)

        phases = [int(i) for i in tit.group("phases").split(',')]
        if set(np.diff(phases)) != {1}:
            raise IOError("Phases must be sequencial in "+ path)

        starts  = output['phases'][:, phases[0]] - output['phases'][0,phases[0]]
        bead    = output[beadid]
        bead[:] = np.NaN
        for title, vals in grdict.items():
            tit = cls.__GRTITLE.match(title)
            if tit is None:
                continue

            cyc  = int(tit.group("id")) - output['cyclemin']
            inds = np.int32(vals[0]+.1+starts[cyc]) # type: ignore
            bead[inds] = vals[1]
        return beadid

_CALLERS = _TrackIO.__subclasses__()

class Handler:
    u"A handler for opening the provided path"
    def __init__(self, path: str, handler: Any) -> None:
        self.path    = path
        self.handler = handler

    def __call__(self, track, beadsonly = False) -> "Track":
        from .track import Track    # pylint: disable=redefined-outer-name
        if not isinstance(track, Track):
            track = Track(path = self.path)
        else:
            track.path = self.path

        track = self.handler.open(track)
        if beadsonly:
            for key in {i for i in track.data if not track.isbeadname(i)}:
                track.data.pop(key) # pylint: disable=no-member
        return track

    @classmethod
    def check(cls, track) -> 'Handler':
        u"""
        Checks that a path exists without actually opening the track.

        It raises an IOError in case the provided path does not exist or
        cannot be handled.

        Upon success, it returns a handler with the correct protocol for this path.
        """
        paths = getattr(track, 'path', track)
        if isinstance(paths, (str, Path)):
            if not Path(paths).exists():
                raise IOError("Could not find path: " + str(paths))
        else:
            paths = tuple(str(i) for i in paths)

        for caller in _CALLERS:
            tmp = caller.check(paths)
            if tmp is not None:
                res = cls(tmp, caller)
                break
        else:
            raise IOError("Unknown file format in: {}".format(paths))

        return res

def checkpath(track) -> Handler:
    u"""
    Checks that a path exists without actually opening the track.

    It raises an IOError in case the provided path does not exist or
    cannot be handled.

    Upon success, it returns a handler with the correct protocol for this path.
    """
    return Handler.check(track)

def opentrack(track, beadsonly = False):
    u"Opens a track depending on its extension"
    checkpath(track)(track, beadsonly)
