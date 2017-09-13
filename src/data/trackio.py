#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=arguments-differ
u"Loading and save tracks"
from    typing      import (Sequence, Callable,
                            Any, Union, Tuple, Optional, Iterator, Dict,
                            TYPE_CHECKING)
from    itertools   import chain
from    inspect     import signature
import  pickle
import  re
from    functools   import wraps, partial
from    pathlib     import Path
import  numpy       as     np

from    legacy      import readtrack, readgr # pylint: disable=import-error,no-name-in-module
if TYPE_CHECKING:
    from data.track import Track  # pylint: disable=unused-import

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
    return Path(root).glob(path[ind:])

def _checktype(fcn):
    sig = signature(fcn)
    tpe = tuple(i for i in sig.parameters.values()
                if i.kind is not i.VAR_KEYWORD)[-1].annotation
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
    def check(path, **_):
        u"checks the existence of a path"
        raise NotImplementedError()

    @staticmethod
    def open(path, **_):
        u"opens a track file"
        raise NotImplementedError()

class PickleIO(_TrackIO):
    u"checks and opens pickled paths"
    @staticmethod
    @_checktype
    def check(path:PATHTYPE, **_) -> Optional[PATHTYPE]:
        u"checks the existence of a path"
        return path if Path(path).suffix == ".pk" else None

    @staticmethod
    def open(path:PATHTYPE, **_) -> dict:
        u"opens a track file"
        with open(str(path), 'rb') as stream:
            return pickle.load(stream)

class LegacyTrackIO(_TrackIO):
    u"checks and opens legacy track paths"
    __TRKEXT = '.trk'
    @classmethod
    @_checktype
    def check(cls, path:PATHTYPE, **_) -> Optional[PATHTYPE]: # type: ignore
        u"checks the existence of a path"
        return path if Path(path).suffix == cls.__TRKEXT else None

    @staticmethod
    def open(path:PATHTYPE, **kwa) -> dict:
        u"opens a track file"
        axis = kwa.pop('axis', 'Z')
        axis = getattr(axis, 'value', axis)[0]
        return readtrack(str(path), kwa.pop('notall', True), axis)

    @classmethod
    def scan(cls, trkdirs) -> Iterator[Path]:
        "scan for track files"
        if not isinstance(trkdirs, (tuple, list, set, frozenset)):
            trkdirs = (trkdirs,)
        trkdirs = tuple(str(i) for i in trkdirs)

        trk = cls.__TRKEXT
        fcn = lambda i: i if i.endswith(trk) else i+'/**/*'+trk
        yield from (i for i in chain.from_iterable(_glob(fcn(str(k))) for k in trkdirs))

class LegacyGRFilesIO(_TrackIO):
    u"checks and opens legacy GR files"
    __TRKEXT = '.trk'
    __GREXT  = '.gr'
    __CGREXT = '.cgr'
    __GRDIR  = 'cgr_project'
    __TITLE  = re.compile(r"\\stack{{Bead (?P<id>\d+) Z.*?phase\(s\)"
                          +r"(?:[^\d]|\d(?!,))*(?P<phases>[\d, ]*?)\]}}")
    __GRTITLE = re.compile(r"Bead Cycle (?P<id>\d+) p.*")
    @classmethod
    @_checktype
    def check(cls, # type: ignore
              apaths:Tuple[PATHTYPE,...],
              **kwa) -> Optional[Tuple[PATHTYPE,...]]:
        u"checks the existence of paths"
        if len(apaths) < 2:
            return None

        paths = tuple(Path(i) for i in apaths)
        if sum(1 for i in paths if i.suffix == cls.__TRKEXT) != 1:
            return None

        if len(paths) == 2 and any(i.is_dir() for i in paths):
            paths = cls.__findgrs(paths, kwa)
            fname = str(paths[0])
            if '*' in fname:
                return cls.__findtrk(fname, paths[1])

            elif not paths[0].exists():
                raise IOError("Could not find path: " + str(paths[0]), "warning")

            return paths

        else:
            trk = next(i for i in paths if i.suffix == cls.__TRKEXT)
            grs = tuple(i for i in paths if i.suffix  == '.gr')
            if len(grs) == 0:
                return None

            return (trk,) + grs

    @classmethod
    def open(cls, paths:Tuple[PATHTYPE,PATHTYPE], **kwa) -> dict: # type: ignore
        u"opens the directory"
        output = LegacyTrackIO.open(paths[0], **kwa)
        if output is None:
            raise IOError(f"Could not open track '{paths[0]}'.\n"
                          "This could be because of a *root* mounted samba path")
        remove = set(i for i in output if isinstance(i, int))

        if len(paths) == 2 and Path(paths[1]).is_dir():
            itr : Iterator[Path] = iter(i for i in Path(paths[1]).iterdir()
                                        if 'z(t)bd' in i.stem.lower())
        else:
            itr = (Path(i) for i in paths[1:])

        # in case of axis != 'Z: we keep a backup,
        # find which beads are valid and recover only these
        axis   = kwa.pop('axis', 'Z')
        axis   = getattr(axis, 'value', axis)[0]
        backup = dict(output) if axis != 'Z' else output

        for grpath in itr:
            if grpath.suffix == ".gr":
                remove.discard(cls.__update(str(grpath), output))

        output = backup # this only affects axis != 'Z'
        for key in remove:
            output.pop(key)
        return output

    @classmethod
    def __findgrs(cls, paths, opts):
        grdir  = opts.get('cgrdir', cls.__GRDIR)
        ext    = cls.__GREXT, cls.__CGREXT
        err    = lambda j: IOError(j+'\n -'+ '\n -'.join(str(i) for i in paths), 'warning')
        hasgr  = lambda i: (i.is_dir()
                            and (i.name == grdir
                                 or any(j.suffix in ext for j in i.iterdir())))

        grs    = [hasgr(i) for i in paths]
        direct = sum(i for i in grs)

        if direct == 0:
            grs    = [hasgr(i/grdir) for i in paths]
            direct = sum(i for i in grs)

            if direct == 0:
                raise err("No .gr files in directory:")

            elif direct > 1:
                raise err("All sub-directories have .gr files:")

            return paths[1 if grs[0] else 0], paths[0 if grs[0] else 1]/grdir

        elif direct > 1:
            raise err("All directories have .gr files:")

        return paths[1 if grs[0] else 0], paths[0 if grs[0] else 1]

    @classmethod
    def __findtrk(cls, fname:str, grs:PATHTYPE) -> Tuple[PATHTYPE,PATHTYPE]:
        cgr  = next((i for i in Path(grs).iterdir() if i.suffix == cls.__CGREXT),
                    None)
        if cgr is None:
            raise IOError(f"No {cls.__CGREXT} files in directory\n- {grs}", "warning")

        pot = cgr.with_suffix(cls.__TRKEXT).name
        trk = next((i for i in _glob(fname) if i.name == pot), None)
        if trk is None:
            raise IOError(f"Could not find {pot} in {fname}", "warning")
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
    def __scan(cls, lst, fcn) -> Dict[str, Path]:
        return {i.stem: i for i in chain.from_iterable(_glob(fcn(str(k))) for k in lst)}

    @classmethod
    def scantrk(cls, trkdirs) -> Dict[str, Path]:
        "scan for track files"
        return {i.stem: i for i in LegacyTrackIO.scan(trkdirs)}

    @classmethod
    def scangrs(cls, grdirs, **opts) -> Dict[str, Path]:
        "scan for gr files"
        if not isinstance(grdirs, (tuple, list, set, frozenset)):
            grdirs = (grdirs,)

        grdirs   = tuple(str(i) for i in grdirs)
        projects = opts.get("cgrdir", cls.__GRDIR)
        if isinstance(projects, str):
            projects = (projects,)

        res = {}
        fcn = lambda match, grdir, i: (i if match(i) or cls.__CGREXT in i else i + grdir)
        for proj in projects:
            if proj:
                grdir = f'/**/{proj}/*{cls.__CGREXT}'
                part  = partial(fcn, re.compile(rf'\b{proj}\b').search, grdir)
            else:
                grdir = f'/**/*{cls.__CGREXT}'
                part  = partial(fcn, lambda _: False, grdir)
            res.update(cls.__scan(grdirs, part))
        return res

    @classmethod
    def scan(cls,
             trkdirs: Union[str, Sequence[str]],
             grdirs:  Union[str, Sequence[str]],
             matchfcn: Callable[[Path, Path], bool] = None, **opts):
        """
        Scans for pairs

        Returns:

            * pairs of (trk file, gr directory)
            * gr directories with missing trk files
            * trk files with missing gr directories
        """
        grdirs  = (grdirs,)  if isinstance(grdirs,  (Path, str)) else grdirs  # type: ignore
        trkdirs = (trkdirs,) if isinstance(trkdirs, (Path, str)) else trkdirs # type: ignore

        trks    = cls.scantrk(trkdirs)
        cgrs    = cls.scangrs(grdirs, **opts)

        if matchfcn is None:
            pairs    = frozenset(trks) & frozenset(cgrs)
            good     = tuple((trks[i], cgrs[i].parent) for i in pairs)
            lonegrs  = tuple(cgrs[i].parent for i in frozenset(cgrs) - pairs)
            lonetrks = tuple(trks[i]        for i in frozenset(trks) - pairs)
        else:
            tgood     = []
            tlonetrks = []
            for trk in trks.values():
                key = next((j for j in cgrs.values() if matchfcn(trk, j)), None)
                if key is None:
                    tlonetrks.append(trk)
                else:
                    tgood.append((trk, key.parent))
                    cgrs.pop(key.stem)
            good     = tuple(tgood)
            lonetrks = tuple(tlonetrks)
            lonegrs  = tuple(i.parent for i in cgrs.values())

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

        res    = dict(lazy   = False,
                      notall = getattr(track, 'notall', True),
                      axis   = getattr(track, 'axis',   'Zaxis'))
        kwargs = self.handler.open(path, **res)
        res['path'] = path
        if kwargs is None:
            res['data'] = {}
        else:
            self.__fov(res, kwargs)
            res.update({i: kwargs.pop(i) for i in ('phases', 'framerate')})

            if beadsonly:
                data = {i: j for i, j in kwargs.items()
                        if Track.isbeadname(i) and isinstance(j, np.ndarray)}
            else:
                data = {i: j for i, j in kwargs.items()
                        if isinstance(j, np.ndarray)}
            res['data'] = data

        if track is None:
            return Track(**res)

        track.__setstate__(res)
        return track

    @classmethod
    def check(cls, track, **opts) -> 'Handler':
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
            tmp = caller.check(paths, **opts)
            if tmp is not None:
                res = cls(tmp, caller)
                break
        else:
            raise IOError("Unknown file format in: {}".format(paths), "warning")

        return res

    @staticmethod
    def __fov(res, kwargs):
        from .track import FoV, Bead
        calib = kwargs.pop('calibrations', {})
        res['fov'] = FoV()
        if 'fov' in kwargs:
            res['fov'].image = kwargs.pop('fov')

        if 'dimensions' in kwargs:
            res['fov'].dim   = kwargs.pop('dimensions')

        if 'positions' in kwargs:
            res['fov'].beads = {i: Bead(position = j,
                                        image    = calib.get(i, Bead.image))
                                for i, j in kwargs.pop('positions', {}).items()
                                if i in kwargs}

def checkpath(track, **opts) -> Handler:
    u"""
    Checks that a path exists without actually opening the track.

    It raises an IOError in case the provided path does not exist or
    cannot be handled.

    Upon success, it returns a handler with the correct protocol for this path.
    """
    return Handler.check(track, **opts)

def opentrack(track, beadsonly = False):
    u"Opens a track depending on its extension"
    checkpath(track)(track, beadsonly)
