#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Task IO module"
from typing             import Union, Tuple
from pathlib            import Path
from itertools          import chain
from copy               import deepcopy
from model.task         import TrackReaderTask
from utils.logconfig    import getLogger
LOGS = getLogger(__name__)

class TaskIO:
    u"base class for opening files"
    def __init__(self, *_):
        pass

    # pylint: disable=no-self-use,unused-argument
    def open(self, path:Union[str, Tuple[str,...]], model:tuple):
        u"opens a file"
        return None

    def save(self, path:str, models):
        u"saves a file"
        return None

    @classmethod
    def __get(cls, ctrl, attr:str):
        ctrl = getattr(ctrl, 'taskcontroller', ctrl)
        return getattr(ctrl, '_TaskController__'+attr)

    @classmethod
    def extensions(cls, ctrl, attr:str):
        "returns the list of possible extensions"
        return '|'.join(chain.from_iterable(i.EXT for i in cls.__get(ctrl, attr)[::-1]))

class TrackIO(TaskIO):
    "Deals with reading a track file"
    EXT = ('trk',) # type: Tuple[str, ...]
    def open(self, path:Union[str, Tuple[str,...]], model:tuple):
        "opens a track file"
        if len(model):
            raise NotImplementedError()
        LOGS.info('%s -> path = %s', type(self).__name__, path)
        return [(TrackReaderTask(path = path),)]

class ConfigTrackIO(TrackIO):
    "Adds an alignment to the tracks per default"
    def __init__(self, ctrl, *_):
        super().__init__(ctrl, *_)
        self._ctrl = ctrl.getGlobal('config').tasks

    def open(self, path:Union[str, Tuple[str,...]], model:tuple):
        "opens a track file and adds a alignment"
        if isinstance(path, str):
            path = (path,)

        items = [TrackIO.open(self, path, model)[0][0]]
        for name in self._ctrl.get(default = tuple()):
            task = self._ctrl[name].get(default = None)
            if not getattr(task, 'disabled', True):
                items.append(deepcopy(task))
        return [tuple(items)]

class _GrFilesIOMixin:
    "Adds an alignment to the tracks per default"
    EXT = TrackIO.EXT+('gr',) # type: Tuple[str, ...]
    def __init__(self, ctrl):
        self._track = None
        fcn         = lambda itm: setattr(self, '_track', itm.value)
        ctrl.getGlobal('project').track.observe(fcn)

    def _open(self, path:Union[str, Tuple[str,...]], _):
        "opens a track file and adds a alignment"
        if isinstance(path, str):
            path = (path,)

        trks = tuple(i for i in path if any(i.endswith(j) for j in TrackIO.EXT))
        grs  = tuple(i for i in path if i.endswith(self.EXT[-1]) or Path(i).is_dir())
        if len(trks) + len(grs) < len(path) or len(trks) > 1 or len(grs) < 1:
            return None

        if len(trks) == 0:
            track = self._track
            if track is None:
                raise IOError(u"IOError: start by opening a track file!", "warning")

            return ((track.path,) if isinstance(track.path, str) else track.path) + path
        else:
            return trks+grs

class GrFilesIO(TrackIO, _GrFilesIOMixin):
    "Adds an alignment to the tracks per default"
    EXT = _GrFilesIOMixin.EXT
    def __init__(self, *_):
        TrackIO.__init__(self, *_)
        _GrFilesIOMixin.__init__(self, *_)

    def open(self, path:Union[str, Tuple[str,...]], _:tuple):
        path = self._open(path, _)
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

    def open(self, path:Union[str, Tuple[str,...]], _:tuple):
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
