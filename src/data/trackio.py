#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=arguments-differ
"Loading and save tracks"
import  sys
from    typing             import (Sequence, Any, Union, Tuple, Optional,
                                   Iterator, Dict, cast, overload, TypeVar,
                                   TYPE_CHECKING)
from    abc                import ABC, abstractmethod
from    itertools          import chain
from    concurrent.futures import ThreadPoolExecutor
from    copy               import copy as shallowcopy
from    functools          import partial
from    pathlib            import Path
import  pickle
import  re
import  numpy              as     np

# pylint: disable=import-error,no-name-in-module
from    legacy             import readtrack, readgr, fov as readfov

if TYPE_CHECKING:
    # pylint: disable=unused-import
    from data.track      import Track
    from data.tracksdict import TracksDict
    TDICT_T = TypeVar('TDICT_T', bound = 'TracksDict')
else:
    TDICT_T = 'TracksDict'

PATHTYPE  = Union[str, Path]
PATHTYPES = Union[PATHTYPE,Tuple[PATHTYPE,...]]

def _glob(path:str):
    ind1 = path.find('*')
    ind2 = path.find('[')
    ind  = ind1 if ind2 == -1 else ind2 if ind1 == -1 else min(ind1, ind2)
    if ind == -1:
        return Path(path)

    root = Path(path[:ind])
    if path[ind-1] not in ('/', '\\') and root != Path(path).parent:
        return Path(str(root.parent)).glob(root.name+path[ind:])
    return Path(root).glob(path[ind:])

class _TrackIO(ABC):
    @classmethod
    @abstractmethod
    def check(cls, path:PATHTYPES, **_) -> Optional[PATHTYPES]:
        "checks the existence of a path"

    @staticmethod
    def checkpath(path:PATHTYPES, ext:str) -> Optional[PATHTYPES]:
        "checks the existence of a path"
        if isinstance(path, (tuple, list, set, frozenset)) and len(path) == 1:
            path = path[0]
        if isinstance(path, (str, Path)):
            return path if Path(path).suffix == ext else None
        return None

    @classmethod
    @abstractmethod
    def open(cls, path:PATHTYPE, **_) -> Dict[Union[str, int], Any]:
        "opens a track file"

class PickleIO(_TrackIO):
    "checks and opens pickled paths"
    EXT = '.pk'
    @classmethod
    def check(cls, path:PATHTYPES, **_) -> Optional[PATHTYPES]:
        "checks the existence of a path"
        return cls.checkpath(path, cls.EXT)

    @staticmethod
    def open(path:PATHTYPE, **_) -> Dict[Union[str, int], Any]:
        "opens a track file"
        with open(path, 'rb') as stream:
            return pickle.load(stream)

    @classmethod
    def save(cls, path: PATHTYPE, track: Union[dict, 'Track']):
        "saves a track file"
        info = track if isinstance(track, dict) else Handler.todict(track)
        with open(path, 'wb') as stream:
            return pickle.dump(info, stream)

class LegacyTrackIO(_TrackIO):
    "checks and opens legacy track paths"
    TRKEXT = '.trk'
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

    @classmethod
    def scan(cls, trkdirs) -> Iterator[Path]:
        "scan for track files"
        if not isinstance(trkdirs, (tuple, list, set, frozenset)):
            trkdirs = (trkdirs,)
        trkdirs = tuple(str(i) for i in trkdirs)
        if all(Path(i).is_dir() for i in trkdirs):
            for trk in (cls.TRKEXT, PickleIO.EXT):
                end = f'/**/*{trk}'
                lst = [i for i in chain.from_iterable(_glob(str(k)+end) for k in trkdirs)]
                if len(lst):
                    yield from iter(lst)
                    break
            return

        trk = cls.TRKEXT
        fcn = lambda i: i if '*' in i or i.endswith(trk) else i+'/**/*'+trk
        yield from (i for i in chain.from_iterable(_glob(fcn(str(k))) for k in trkdirs))

class LegacyGRFilesIO(_TrackIO):
    "checks and opens legacy GR files"
    TRKEXT    = '.trk'
    GREXT     = '.gr'
    CGREXT    = '.cgr'
    __GRDIR   = 'cgr_project'
    __TITLE   = re.compile(r"\\stack{{Bead (?P<id>\d+) Z.*?phase\(s\)"
                           r"(?:[^\d]|\d(?!,))*(?P<phases>[\d, ]*?)\].*?}}")
    __GRTITLE = re.compile(r"Bead Cycle (?P<id>\d+) p.*")
    @classmethod
    def check(cls, path:PATHTYPES, **kwa) -> Optional[PATHTYPES]:
        "checks the existence of paths"
        if not isinstance(path, (list, tuple, set, frozenset)) or len(path) < 2:
            return None

        allpaths = tuple(Path(i) for i in cast(Tuple[PATHTYPE,...], path))
        if sum(1 for i in allpaths if i.suffix == cls.TRKEXT) != 1:
            return None

        if any(i.suffix == cls.CGREXT for i in allpaths):
            if len(allpaths) == 2:
                allpaths = tuple(i if i.suffix == cls.TRKEXT else i.parent for i in allpaths)
            else:
                allpaths = tuple(i for i in allpaths if i.suffix != cls.CGREXT)

        if len(allpaths) == 2 and any(i.is_dir() for i in allpaths):
            allpaths = cls.__findgrs(allpaths, kwa)
            fname    = str(allpaths[0])
            if '*' in fname:
                return cls.__findtrk(fname, allpaths[1])

            elif not allpaths[0].exists():
                raise IOError("Could not find path: " + str(allpaths[0]), "warning")

            return allpaths

        else:
            trk = next(i for i in allpaths if i.suffix == cls.TRKEXT)
            grs = tuple(i for i in allpaths if i.suffix  == cls.GREXT)
            if len(grs) == 0:
                return None

            return (trk,) + grs

    @classmethod
    def open(cls, paths:Tuple[PATHTYPE,PATHTYPE], **kwa) -> dict: # type: ignore
        "opens the directory"
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
        ext    = (cls.GREXT,)
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
        cgr  = next((i for i in Path(grs).iterdir() if i.suffix == cls.CGREXT),
                    None)
        if cgr is None:
            raise IOError(f"No {cls.CGREXT} files in directory\n- {grs}", "warning")

        pot = cgr.with_suffix(cls.TRKEXT).name
        trk = next((i for i in _glob(fname) if i.name == pot), None)
        if trk is None:
            raise IOError(f"Could not find {pot} in {fname}", "warning")
        return trk, grs

    @classmethod
    def __update(cls, path:str, output:dict) -> int:
        "verifies one gr"
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
            try:
                bead[inds] = vals[1]
            except IndexError as err:
                raise IOError(f"updating {path} raised {err.__str__}")
        return beadid

    @classmethod
    def __scan(cls, lst, fcn) -> Dict[str, Path]:
        return {i.stem: i for i in chain.from_iterable(_glob(fcn(str(k))) for k in lst)}

    @classmethod
    def scantrk(cls, trkdirs) -> Dict[str, Path]:
        "scan for track files"
        if not isinstance(trkdirs, (tuple, list, set, frozenset)):
            trkdirs = (trkdirs,)
        return {i.stem: i for i in LegacyTrackIO.scan(trkdirs)}

    @classmethod
    def scangrs(cls, grdirs, cgrdir = None, allleaves = False, **_) -> Dict[str, Path]:
        "scan for gr files"
        if not isinstance(grdirs, (tuple, list, set, frozenset)):
            grdirs = (grdirs,)

        grdirs   = tuple(str(i) for i in grdirs)
        projects = ((None,)         if allleaves                else
                    (cgrdir,)       if isinstance(cgrdir, str)  else
                    (cls.__GRDIR,)  if cgrdir is None           else
                    cgrdir)

        res = {}
        fcn = lambda match, grdir, i: (i if match(i) or cls.CGREXT in i else i + grdir)
        for proj in projects:
            if proj:
                grdir = f'/**/{proj}/*{cls.CGREXT}'
                part  = partial(fcn, re.compile(rf'\b{proj}\b').search, grdir)
            elif not allleaves:
                part  = partial(fcn, lambda _: False, '')
            else:
                grdir = f'/**/*.gr'
                part  = partial(fcn, lambda _: '*' in _, grdir)

            update = cls.__scan(grdirs, part)
            if allleaves:
                # add check on gr-files
                res.update({Path(_).parent.stem: Path(_).parent
                            for _ in update.values()
                            if cls.GREXT in _.suffixes})
            else:
                res.update(update)
        return res

    @classmethod
    def scan(cls,
             trkdirs: Union[str, Sequence[str]],
             grdirs:  Union[str, Sequence[str]],
             **opts
            ) -> Tuple[Tuple[PATHTYPES,...], Tuple[PATHTYPES,...], Tuple[PATHTYPES,...]]:
        """
        Scans for pairs

        Returns:

            * pairs of (trk file, gr directory)
            * gr directories with missing trk files
            * trk files with missing gr directories
        """
        trks     = cls.scantrk(trkdirs)
        cgrs     = cls.scangrs(grdirs, **opts)
        rep      = lambda i: i.parent if i.is_file() else i
        pairs    = frozenset(trks) & frozenset(cgrs)
        good     = tuple((trks[i], rep(cgrs[i])) for i in pairs)
        lonegrs  = tuple(rep(cgrs[i])            for i in frozenset(cgrs) - pairs)
        lonetrks = tuple(trks[i]                 for i in frozenset(trks) - pairs)
        return good, lonegrs, lonetrks

_CALLERS = _TrackIO.__subclasses__

class Handler:
    "A handler for opening the provided path"
    def __init__(self, path: PATHTYPES, handler: Any) -> None:
        self.path    = path
        self.handler = handler

    def __call__(self, track = None) -> "Track":
        path = self.path
        if (not isinstance(path, (str, Path))) and len(path) == 1:
            path = path[0]

        if track is None:
            from .track import Track as _Track
            track = _Track()

        kwargs = self.handler.open(path,
                                   notall = getattr(track, 'notall', True),
                                   axis   = getattr(track, 'axis',   'Zaxis'))
        state  = track.__getstate__()
        self.__fov (state, kwargs)
        self.__data(state, kwargs)

        state.update(kwargs)
        state.update(path = path)
        track.__setstate__(state)
        return track

    @classmethod
    def todict(cls, track: 'Track') -> Dict[str, Any]:
        "the oposite of __call__"
        data = dict(track.data) # get the data first because of lazy instantiations
        data.update(track.__getstate__())

        data['fov']          = track.fov.image
        data['dimensions']   = track.fov.dim
        data['positions']    = {i: j.position for i, j in track.fov.beads.items()}
        data['calibrations'] = {i: j.image    for i, j in track.fov.beads.items()}

        # add a modification date as the original one is needed
        if hasattr(track, '_modificationdate'):
            data['_modificationdate'] = getattr(track, '_modificationdate')
        elif track.path:
            path = (Path(str(track.path[0]))
                    if isinstance(track.path, (list, tuple)) else
                    Path(str(track.path)))
            data['_modificationdate'] = path.stat().st_mtime

        sec = track.secondaries.data
        if sec:
            data.update((i, sec.pop(i)) for i  in set(sec) & {'zmag', 't'})
            vcap = sec.pop('vcap', None)
            if vcap is not None:
                data['vcap']  = vcap['index'], vcap['zmag'], vcap['vcap']
            data.update({i: (j['index'], j['value']) for i, j in sec.items()})
        return data

    @classmethod
    def check(cls, track, **opts) -> 'Handler':
        """
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
            if getattr(getattr(track,"axis", None), 'value', 'Z')[0] != "Z":
                raise ValueError(f"Cannot read XY axes with gr files")
            for i in paths:
                if '*' in i:
                    if next(_glob(i), None) is None:
                        raise IOError("Path yields no file: " + i, "warning")

                elif not Path(i).exists():
                    raise IOError("Could not find path: " + i, "warning")

        for caller in _CALLERS():
            tmp = caller.check(paths, **opts)
            if tmp is not None:
                res = cls(tmp, caller)
                break
        else:
            raise IOError("Unknown file format in: {}".format(paths), "warning")

        return res

    @staticmethod
    def __data(state, kwargs):
        if kwargs is None:
            data = {} # type: Dict[str, Union[float, np.ndarray, str]]
            sec  = {} # type: Dict[str, np.ndarray]
        else:
            dtpe = np.dtype([('index', 'i4'), ('value', 'f4')])
            vtpe = [('index', 'f4'), ('zmag',  'f4'), ('vcap',  'f4')]
            sec  = {i: np.array(list(zip(*kwargs.pop(i))),
                                dtype = dtpe if i[0] == 'T' else vtpe)
                    for i in ('vcap', 'Tservo', 'Tsink', 'Tsample') if i in kwargs}
            sec.update({i: kwargs.pop(i) for i in set(kwargs) & {"t", "zmag"}})

            data = {i: kwargs.pop(i) for i in tuple(kwargs)
                    if isinstance(kwargs[i], np.ndarray) and len(kwargs[i].shape) == 1}
        state['data']        = data
        state['secondaries'] = sec

    @staticmethod
    def __fov(res, kwargs):
        if kwargs is None:
            return

        from .track import FoV, Bead
        calib = kwargs.pop('calibrations', {})
        res['fov'] = FoV()
        if 'fov' in kwargs:
            res['fov'].image = kwargs.pop('fov')
            if res['fov'].image is None and sys.platform.startswith("win"):
                if isinstance(res['path'], (list, tuple)):
                    path = str(res['path'][0])
                else:
                    path = str(res['path'])
                res['fov'].image = readfov(path)

        if 'dimensions' in kwargs:
            res['fov'].dim   = kwargs.pop('dimensions')

        if 'positions' in kwargs:
            res['fov'].beads = {i: Bead(position = j,
                                        image    = calib.get(i, Bead.image))
                                for i, j in kwargs.pop('positions', {}).items()
                                if i in kwargs}

def checkpath(track, **opts) -> Handler:
    """
    Checks that a path exists without actually opening the track.

    It raises an IOError in case the provided path does not exist or
    cannot be handled.

    Upon success, it returns a handler with the correct protocol for this path.
    """
    return Handler.check(track, **opts)

def opentrack(track):
    "Opens a track depending on its extension"
    checkpath(track)(track)

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
def savetrack(path: PATHTYPE, track: 'Track') -> 'Track': # pylint: disable=unused-argument
    "saves a track"
    pass

@overload
def savetrack(path  : PATHTYPE,     # pylint: disable=unused-argument,function-redefined
              track : TDICT_T       # pylint: disable=unused-argument
             ) -> TDICT_T:
    "saves a tracksdict"
    pass

def savetrack(path  : PATHTYPE,     # pylint: disable=unused-argument,function-redefined
              track : Union['Track', Dict[str,'Track']]
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
