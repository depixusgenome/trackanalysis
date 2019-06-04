#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=arguments-differ
"Loading and save tracks"
import  sys
from    typing    import Any, Union, Dict, TYPE_CHECKING
from    pathlib   import Path
import  numpy     as     np

# pylint: disable=import-error,no-name-in-module
from    legacy    import fov as readfov
from    ._base    import TrackIO, globfiles, PATHTYPES
if TYPE_CHECKING:
    from    ._base import Track

_CALLERS = lambda: sorted(TrackIO.__subclasses__(), key = lambda i: -i.PRIORITY)

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
        self.__instrument(state, kwargs)
        self.__fov (state, kwargs)
        self.__data(state, kwargs)
        if isinstance(kwargs.get("tasks", None), str):
            import taskstore as _ana
            kwargs['tasks'] = _ana.loads(kwargs['tasks'])

        state.update(kwargs)
        state.update(path = path)
        track.__setstate__(state)
        return track

    def instrumenttype(self) -> str:
        "return the instrument type"
        path = self.path[0] if isinstance(self.path, (list, tuple)) else self.path
        return self.handler.instrumenttype(str(path))

    @classmethod
    def todict(cls, track: 'Track') -> Dict[str, Any]:
        "the oposite of __call__"
        data = dict(track.data) # get the data first because of lazy instantiations
        data.update(track.__getstate__())
        if 'tasks' in data:
            import taskstore as _ana
            data['tasks'] = _ana.dumps(data['tasks'])

        data['fov']          = track.fov.image
        data['dimensions']   = track.fov.dim
        data['positions']    = {i: j.position for i, j in track.fov.beads.items()}
        data['calibrations'] = {i: j.image    for i, j in track.fov.beads.items()}
        data["instrument"]   = track.instrument

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
                    if next(globfiles(i), None) is None:
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
            data: Dict[str, Union[float, np.ndarray, str]] = {}
            sec : Dict[str, np.ndarray]                    = {}
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
        state['phases']      = kwargs.pop('phases').astype('i4')

    def __instrument(self, res, kwargs):
        if kwargs is not None and 'instrument' in kwargs:
            res['instrument'] = kwargs.pop("instrument")
            assert "type" in res['instrument']
        else:
            res['instrument'] = {"type": self.instrumenttype(), "name": None}
        res['instrument'].setdefault("dimension", "µm")

    @staticmethod
    def __fov(res, kwargs):
        if kwargs is None:
            return

        res['fov'] = {}
        if 'fov' in kwargs:
            res['fov']['image'] = kwargs.pop('fov')
            if res['fov']['image'] is None and sys.platform.startswith("win"):
                if isinstance(res['path'], (list, tuple)):
                    path = str(res['path'][0])
                else:
                    path = str(res['path'])
                res['fov']['image'] = readfov(path)

        if 'dimensions' in kwargs:
            res['fov']['dim']   = kwargs.pop('dimensions')

        calib = kwargs.pop('calibrations', {})
        if 'positions' in kwargs:
            res['fov']['beads'] = {i: dict(position = j, image = calib.get(i, None))
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

def instrumenttype(track) -> str:
    "return the instrument type"
    return checkpath(getattr(track, 'path', track)).instrumenttype()
