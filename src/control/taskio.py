#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Task IO module"
from typing             import Union, Iterable, Tuple, Dict, cast
from pathlib            import Path
from itertools          import chain
from copy               import deepcopy
from model.task         import TrackReaderTask
from data.tracksdict    import TracksDict
from utils.logconfig    import getLogger
LOGS   = getLogger(__name__)
PATH_T = Union[str, Path]
OPEN_T = Union[PATH_T, Iterable[PATH_T], Dict[str, str]]
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
        ctrl = getattr(ctrl, 'taskcontroller', ctrl)
        return getattr(ctrl, '_BaseTaskController__'+attr)

    @classmethod
    def extensions(cls, ctrl, attr:str):
        "returns the list of possible extensions"
        return '|'.join(chain.from_iterable(i.EXT for i in cls.__get(ctrl, attr)[::-1]))

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
            return

        if isinstance(path, (list, tuple)) and len(path) == 1:
            path = cast(str, path[0])
        LOGS.info('%s loading %s', type(self).__name__, path)
        return [(TrackReaderTask(path = topath(path)),)]

class ConfigTrackIO(TrackIO):
    "Adds an alignment to the tracks per default"
    def __init__(self, ctrl, *_):
        super().__init__(ctrl, *_)
        self._ctrl = ctrl.getGlobal('config').tasks

    def open(self, path:OPEN_T, model:tuple):
        "opens a track file and adds a alignment"
        tmp = TrackIO.open(self, path, model)
        if not tmp or not tmp[0]:
            return None
        items = [tmp[0][0]]
        for name in self._ctrl.get(default = tuple()):
            task = self._ctrl[name].get(default = None)
            if not getattr(task, 'disabled', True):
                items.append(deepcopy(task))
        return [tuple(items)]

class _GrFilesIOMixin:
    "Adds an alignment to the tracks per default"
    EXT: Tuple[str, ...] = TrackIO.EXT+('gr',)
    CGR                  = '.cgr'
    def __init__(self, ctrl):
        self._track = None
        fcn         = lambda itm: setattr(self, '_track', itm.value)
        ctrl.getGlobal('project').track.observe(fcn)

    def _open(self, path:OPEN_T, _):
        "opens a track file and adds a alignment"
        if isinstance(path, dict):
            return

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
            if self._track is None:
                raise IOError(u"IOError: start by opening a track file!", "warning")
            trks = topath(getattr(self._track, 'path'))
        return trks+grs

class GrFilesIO(TrackIO, _GrFilesIOMixin):
    "Adds an alignment to the tracks per default"
    EXT = _GrFilesIOMixin.EXT
    def __init__(self, *_):
        TrackIO.__init__(self, *_)
        _GrFilesIOMixin.__init__(self, *_)

    def open(self, path:OPEN_T, _:tuple):
        if isinstance(path, dict):
            return

        path = self._open(cast(Union[str, Tuple[str,...]], path), _)
        return None if path is None else TrackIO.open(self, path, _)

def currentmodelonly(cls):
    "Adapts a class such that only the current model is saved"
    def __init__(self, ctrl, *_):
        cls.__init__(self, ctrl, *_)
        self.currentmodel = ctrl.getGlobal('project').track.get

    def save(self, path:str, models):
        u"saves a file"
        curr   = self.currentmodel()
        models = [i for i in models if curr is i[0]]
        if len(models):
            return cls.save(self, path, models)
        else:
            raise IOError("Nothing to save", "warning")
        return True

    return type(cls.__name__, (cls,), {'__init__': __init__, 'save': save})

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

        task = type(self._ctrl.extremumalignment.get(default = None))
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
