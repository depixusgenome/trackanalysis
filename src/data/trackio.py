#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Loading and save tracks"
from    typing      import (Sequence, Callable, # pylint: disable=unused-import
                            Any, Union, Tuple, Optional, Iterator, TYPE_CHECKING)
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
PATHTYPES = Union[PATHTYPE,Tuple[PATHTYPE,...]]

def _checktype(fcn):
    sig = signature(fcn)
    tpe = tuple(sig.parameters.values())[-1].annotation
    if tpe is sig.empty:
        tpe = Any
    elif tpe == Tuple[PATHTYPE,...]:
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
        trk    = args[-1]
        path   = trk.path
        if (not isinstance(path, (str, Path))) and len(path) == 1:
            path = path[0]
        kwargs = fcn(*args[:-1]+(path,))

        if kwargs is None:
            trk.data = dict()
        else:
            for name in {'phases', 'framerate'} & set(kwargs):
                setattr(trk, name, kwargs.pop(name))

            trk.data = dict(ite for ite in kwargs.items()
                            if isinstance(ite[1], np.ndarray))
        return trk
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
                           +r"(?:[^\d]|\d(?!,))*(?P<phases>[\d, ]*?)\]}}")
    __GRTITLE = re.compile(r"Bead Cycle (?P<id>\d+) p.*")
    @classmethod
    @_checktype
    def check(cls, apaths:Tuple[PATHTYPE,...] # type: ignore
             ) -> Optional[Tuple[PATHTYPE,...]]:
        u"checks the existence of paths"
        if len(apaths) < 2:
            return None

        paths = tuple(Path(i) for i in apaths)
        if sum(1 for i in paths if i.suffix == '.trk') != 1:
            return None

        if len(paths) == 2 and any(i.is_dir() for i in paths):
            if paths[0].is_dir():
                paths = paths[1], paths[0]

            if all(i.suffix != '.gr' for i in paths[1].iterdir()):
                raise IOError("No .gr files in directory\n- {}".format(paths[1]),
                              "warning")
            fname = str(paths[0])
            if '*' in fname:
                return cls.__findtrk(fname, paths[1])

            elif not paths[0].exists():
                raise IOError("Could not find path: " + str(paths[0]), "warning")

            return paths

        else:
            trk = next(i for i in paths if i.suffix == '.trk')
            grs = tuple(i for i in paths if i.suffix  == '.gr')
            return (trk,) + grs

    @classmethod
    @_fromdict
    def open(cls, paths:Tuple[PATHTYPE,PATHTYPE]) -> dict: # type: ignore
        u"opens the directory"
        output = readtrack(str(paths[0]))
        remove = set(i for i in output if isinstance(i, int))

        if len(paths) == 2 and Path(paths[1]).is_dir():
            itr = iter(i for i in Path(paths[1]).iterdir()
                       if 'z(t)bd' in i.stem.lower()) # type: Iterator[Path]
        else:
            itr = (Path(i) for i in paths[1:])

        for grpath in itr:
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
            raise IOError("No '.cgr' files in directory\n- {}".format(grs), "warning")

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
            raise IOError("Could not find {} in {}".format(pot, fname), "warning")
        return trk, grs

    @classmethod
    def __update(cls, path:str, output:dict) -> int:
        u"verifies one gr"
        grdict = readgr(path)
        tit    = cls.__TITLE.match(grdict['title'].decode("utf8", "replace"))

        if tit is None:
            raise IOError("Could not match title in " + path, "warning")

        beadid = int(tit.group("id"))
        if beadid not in output:
            raise IOError("Could not find bead "+str(beadid)+" in " + path, "warning")

        phases = [int(i) for i in tit.group("phases").split(',') if len(i.strip())]
        if set(np.diff(phases)) != {1}:
            raise IOError("Phases must be sequencial in "+ path, "warning")

        starts  = output['phases'][:, phases[0]] - output['phases'][0,phases[0]]
        bead    = output[beadid]
        bead[:] = np.NaN
        for title, vals in grdict.items():
            if not isinstance(title, bytes):
                continue
            tit = cls.__GRTITLE.match(title.decode("utf8", "replace"))
            if tit is None:
                continue

            cyc  = int(tit.group("id")) - output['cyclemin']
            if cyc >= len(starts):
                continue

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

        if (not isinstance(paths, (str, Path))) and len(paths) == 1:
            paths = paths[0]

        if isinstance(paths, (str, Path)):
            if not Path(paths).exists():
                raise IOError("Could not find path: " + str(paths), "warning")
        else:
            paths = tuple(str(i) for i in paths)

        for caller in _CALLERS:
            tmp = caller.check(paths)
            if tmp is not None:
                res = cls(tmp, caller)
                break
        else:
            raise IOError("Unknown file format in: {}".format(paths), "warning")

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
