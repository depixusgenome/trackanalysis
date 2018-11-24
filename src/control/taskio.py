#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Task IO module"
from typing             import Union, Iterable, Tuple, Dict, cast
from pathlib            import Path
from itertools          import chain
from copy               import deepcopy
from model.task         import TrackReaderTask
from model.task.application import TasksConfig, TasksDisplay, TaskIOTheme
from control.decentralized  import Indirection
from data.trackio       import instrumenttype
from data.tracksdict    import TracksDict
from utils.logconfig    import getLogger
LOGS   = getLogger(__name__)
PATH_T = Union[str, Path] # pylint: disable=invalid-name
OPEN_T = Union[PATH_T, Iterable[PATH_T], Dict[str, str]] # pylint: disable=invalid-name
class TaskIO:
    u"base class for opening files"
    def __init__(self, *_):
        pass

    # pylint: disable=no-self-use,unused-argument
    def open(self, path:OPEN_T, model:tuple):
        u"opens a file"
        return None

    def save(self, path:str, models):
        u"saves a file"
        return None

    @classmethod
    def __get(cls, ctrl, attr:str):
        return getattr(ctrl.tasks, '_'+attr)

    @classmethod
    def extensions(cls, ctrl, attr:str):
        "returns the list of possible extensions"
        itms = list(chain.from_iterable(i.EXT for i in cls.__get(ctrl, attr)[::-1]))
        return '|'.join(j for i, j in enumerate(itms) if j not in itms[:i])

def topath(path:Union[PATH_T, Iterable[PATH_T]]) -> Tuple[Path, ...]:
    "converts the argument to a tuple of paths"
    return cast(Tuple[Path, ...],
                ((Path(path),) if isinstance(path, str)    else
                 (path,)       if isinstance(path, Path)   else
                 tuple(Path(i) for i in cast(Iterable[PATH_T], path))))

class TrackIO(TaskIO):
    "Deals with reading a track file"
    EXT: Tuple[str, ...] = ('trk',)
    def open(self, path:OPEN_T, model:tuple):
        "opens a track file"
        if len(model):
            raise NotImplementedError()

        if isinstance(path, dict):
            return None

        if isinstance(path, (list, tuple)) and len(path) == 1:
            path = cast(str, path[0])
        LOGS.info('%s loading %s', type(self).__name__, path)
        return [(TrackReaderTask(path = topath(path)),)]

class ConfigTrackIO(TrackIO):
    "Adds an alignment to the tracks per default"
    _config = Indirection()
    _io     = Indirection()
    def __init__(self, ctrl, *_):
        super().__init__(ctrl, *_)
        self._ctrl   = ctrl
        self._config = TasksConfig()
        self._io     = TaskIOTheme()

    def open(self, path:OPEN_T, model:tuple):
        "opens a track file and adds a alignment"
        tmp = TrackIO.open(self, path, model)
        if not tmp or not tmp[0]:
            return None

        items = [tmp[0][0]]
        instr = instrumenttype(items[0])
        if instr is None:
            instr = self._config.instrument
        cnf = self._config[instr]
        for name in self._io.tasks:
            task  = cnf.get(name, None)
            if not getattr(task, 'disabled', True):
                items.append(deepcopy(task))
        return [tuple(items)]

class _GrFilesIOMixin:
    "Adds an alignment to the tracks per default"
    EXT: Tuple[str, ...] = TrackIO.EXT+('gr',)
    CGR                  = '.cgr'
    _display             = Indirection()
    def __init__(self, ctrl):
        self._ctrl    = ctrl
        self._display = TasksDisplay()

    def _open(self, path:OPEN_T, _):
        "opens a track file and adds a alignment"
        if isinstance(path, dict):
            return None

        trail = topath(path)
        trks  = tuple(i for i in trail if i.suffix[1:] in TrackIO.EXT)
        grs   = tuple(i for i in trail if i.suffix[1:] == self.EXT[-1] or i.is_dir())
        if any(i.suffix == self.CGR for i in trail):
            if len(grs) == 0:
                grs   = tuple(set(i.parent for i in trail if i.suffix == self.CGR))
                trail = trks + grs
            else:
                trail = tuple(i for i in trail if i.suffix != self.CGR)

        if len(trks) + len(grs) < len(trail) or len(trks) > 1 or len(grs) < 1:
            return None

        if len(trks) == 0:
            track = self._display.roottask
            if track is None:
                raise IOError(u"IOError: start by opening a track file!", "warning")
            trks = topath(getattr(track, 'path'))
        return trks+grs

class GrFilesIO(TrackIO, _GrFilesIOMixin):
    "Adds an alignment to the tracks per default"
    EXT = _GrFilesIOMixin.EXT
    def __init__(self, *_):
        TrackIO.__init__(self, *_)
        _GrFilesIOMixin.__init__(self, *_)

    def open(self, path:OPEN_T, _:tuple):
        if isinstance(path, dict):
            return None

        path = self._open(cast(Union[str, Tuple[str,...]], path), _)
        return None if path is None else TrackIO.open(self, path, _)

class ConfigGrFilesIO(ConfigTrackIO, _GrFilesIOMixin):
    "Adds an alignment to the tracks per default"
    EXT = _GrFilesIOMixin.EXT
    def __init__(self, *_):
        ConfigTrackIO.__init__(self, *_)
        _GrFilesIOMixin.__init__(self, *_)

    def open(self, path:OPEN_T, _:tuple):
        path = self._open(path, _)
        if path is None:
            return None

        mdls = ConfigTrackIO.open(self, path, _)
        if mdls is None:
            return None

        task = type(self._config.tasks.get('extremumalignment', None))
        ret  = []
        for mdl in mdls:
            ret.append(tuple(i for i in mdl if not isinstance(i, task)))
        return ret

def openmodels(openers, task, tasks):
    "opens all models"
    if isinstance(task, dict):
        models = [] # type: list
        for trk in TracksDict(**cast(dict, task)).values():
            for mdl in openmodels(openers, trk.path, tasks):
                trk.path = mdl[0].path
                models.append((type(mdl[0])(trk, copy = mdl[0].copy),) + mdl[1:])
        if len(models) == 0:
            raise IOError(f"Couldn't open: {task}", 'warning')
        return models

    for obj in openers:
        models = obj.open(task, tasks)
        if models is not None:
            return models

    path = getattr(task, 'path', task)
    if path is None or (isinstance(path, (list, tuple))) and len(path) == 0:
        msg  = "Couldn't open track"

    elif isinstance(path, (tuple, list)):
        msg  = f"Couldn't open: {Path(str(path[0])).name}{', ...' if len(path) else ''}"
    else:
        msg  = f"Couldn't open: {Path(str(path)).name}"

    raise IOError(msg, 'warning')
