#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Loading and save tracks"
from    typing      import (Sequence, Callable, # pylint: disable=unused-import
                            Any, Union, Tuple, Optional, Iterator, TYPE_CHECKING)
from    itertools   import chain
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

def _glob(path:str):
    ind  = path.find('*')
    if ind == -1:
        return path
    assert ind != 0

    root = Path(path[:ind])
    if path[ind-1] not in ('/', '\\') and root != Path(path).parent:
        return Path(str(root.parent)).glob(root.name+path[ind:])
    else:
        return Path(root).glob(path[ind:])

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
    def open(path:PATHTYPE) -> dict:
        u"opens a track file"
        return readtrack(str(path))

class LegacyGRFilesIO(_TrackIO):
    u"checks and opens legacy GR files"
    __CGR     = 'cgr_project'
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
            paths = cls.__findgrs(paths)
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

    @classmethod
    def __findgrs(cls, paths):
        cgr    = cls.__CGR
        err    = lambda j: IOError(j+'\n -'+ '\n -'.join(str(i) for i in paths), 'warning')
        hasgr  = lambda i: (i.is_dir()
                            and (i.name == cgr
                                 or any(j.suffix in ('.gr', '.cgr') for j in i.iterdir())))

        grs    = [hasgr(i) for i in paths]
        direct = sum(i for i in grs)

        if direct == 0:
            grs    = [hasgr(i/cgr) for i in paths]
            direct = sum(i for i in grs)

            if direct == 0:
                raise err("No .gr files in directory:")

            elif direct > 1:
                raise err("All sub-directories have .gr files:")

            return paths[1 if grs[0] else 0], paths[0 if grs[0] else 1]/cgr

        elif direct > 1:
            raise err("All directories have .gr files:")

        return paths[1 if grs[0] else 0], paths[0 if grs[0] else 1]

    @staticmethod
    def __findtrk(fname:str, grs:PATHTYPE) -> Tuple[PATHTYPE,PATHTYPE]:
        cgr  = next((i for i in Path(grs).iterdir() if i.suffix == '.cgr'),
                    None)
        if cgr is None:
            raise IOError("No '.cgr' files in directory\n- {}".format(grs), "warning")

        pot = cgr.with_suffix('.trk').name
        trk = next((i for i in _glob(fname) if i.name == pot), None)
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

        starts  = output['phases'][:, phases[0]] - output['phases'][0,0]
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

    @classmethod
    def scan(cls, trkdirs: Union[str, Sequence[str]], grdirs: Union[str, Sequence[str]]):
        """
        Scans for pairs

        Returns:

            * pairs of (trk file, gr directory)
            * gr directories with missing trk files
            * trk files with missing gr directories
        """
        grdirs  = (grdirs,)  if isinstance(grdirs,  (Path, str)) else grdirs  # type: ignore
        trkdirs = (trkdirs,) if isinstance(trkdirs, (Path, str)) else trkdirs # type: ignore

        cgr    = cls.__CGR
        ichain = lambda lst, fcn: chain.from_iterable(_glob(fcn(str(k))) for k in lst)
        scan   = lambda lst, fcn: {i.stem: i for i in ichain(lst, fcn)}

        trks   = scan(trkdirs, lambda i: i if i.endswith('.trk') else i+'/**/*.trk')
        cgrs   = scan(grdirs,  lambda i: i if cgr in i           else i+'/**/'+cgr+'/*.cgr')

        pairs    = frozenset(trks) & frozenset(cgrs)
        good     = tuple((trks[i], cgrs[i].parent) for i in pairs)
        lonegrs  = tuple(cgrs[i].parent for i in frozenset(cgrs) - pairs)
        lonetrks = tuple(trks[i]        for i in frozenset(trks) - pairs)

        return good, lonegrs, lonetrks

_CALLERS = _TrackIO.__subclasses__()

class Handler:
    u"A handler for opening the provided path"
    def __init__(self, path: str, handler: Any) -> None:
        self.path    = path
        self.handler = handler

    def __call__(self, track = None, beadsonly = False) -> "Track":
        from .track import Track    # pylint: disable=redefined-outer-name

        path = self.path
        if (not isinstance(path, (str, Path))) and len(path) == 1:
            path = path[0]

        kwargs = self.handler.open(path)
        res    = dict(path = path, lazy = False)
        if kwargs is None:
            res['data'] = {}
        else:
            res.update(phases    = kwargs.pop('phases'), # type: ignore
                       framerate = kwargs.pop('framerate'))

            if beadsonly:
                data = {i: j for i, j in kwargs.items()
                        if Track.isbeadname(i) and isinstance(j, np.ndarray)}
            else:
                data = {i: j for i, j in kwargs.items()
                        if isinstance(j, np.ndarray)}
            res['data'] = data

        if track is None:
            return Track(**res)
        else:
            track.__setstate__(res)
            return track

    @classmethod
    def check(cls, track) -> 'Handler':
        u"""
        Checks that a path exists without actually opening the track.

        It raises an IOError in case the provided path does not exist or
        cannot be handled.

        Upon success, it returns a handler with the correct protocol for this path.
        """
        paths = getattr(track, '_path', track)
        if (not isinstance(paths, (str, Path))) and len(paths) == 1:
            paths = paths[0]

        if isinstance(paths, (str, Path)):
            if not Path(paths).exists():
                raise IOError("Could not find path: " + str(paths), "warning")
        else:
            paths = tuple(str(i) for i in paths)
            for i in paths:
                if '*' in i:
                    if next(_glob(i), None) is None:
                        raise IOError("Path yields no file: " + i, "warning")

                elif not Path(i).exists():
                    raise IOError("Could not find path: " + i, "warning")

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
