#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Task IO module"
from typing                import Union, Iterable, Tuple, Dict, List, cast
from pathlib               import Path
from itertools             import chain
from functools             import partial
from copy                  import deepcopy

from control.decentralized import Indirection
from data.trackio          import instrumenttype, MuWellsFilesIO
from data.tracksdict       import TracksDict
from taskmodel             import TrackReaderTask, Task
from taskmodel.application import TasksConfig, TasksDisplay, TaskIOTheme
from utils.logconfig       import getLogger
LOGS     = getLogger(__name__)
PathType = Union[str, Path]
OpenType = Union[PathType, Iterable[PathType], Dict[str, str]]
class TaskIO:
    "base class for opening files"
    def __init__(self, *_):
        pass

    # pylint: disable=no-self-use,unused-argument
    def open(self, path:OpenType, model:tuple):
        "opens a file"
        return None

    def save(self, path:str, models):
        "saves a file"
        return None

    @classmethod
    def __get(cls, ctrl, attr:str):
        return getattr(ctrl.tasks, '_'+attr)

    @classmethod
    def extensions(cls, ctrl, attr:str):
        "returns the list of possible extensions"
        itms = list(chain.from_iterable(i.EXT for i in cls.__get(ctrl, attr)[::-1]))
        return '|'.join(j for i, j in enumerate(itms) if j not in itms[:i])

def topath(path:Union[PathType, Iterable[PathType]]) -> Tuple[Path, ...]:
    "converts the argument to a tuple of paths"
    return cast(Tuple[Path, ...],
                ((Path(path),) if isinstance(path, str)    else
                 (path,)       if isinstance(path, Path)   else
                 tuple(Path(i) for i in cast(Iterable[PathType], path))))

class TrackIO(TaskIO):
    "Deals with reading a track file"
    EXT: Tuple[str, ...] = ('trk',)

    def open(self, path:OpenType, model:tuple):
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
        self._config = ctrl.theme.add(TasksConfig(), False)
        self._io     = ctrl.theme.add(TaskIOTheme(), False)

    def open(self, path:OpenType, model:tuple):
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

    def _open(self, path:OpenType, _):
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
                raise IOError("IOError: start by opening a track file!", "warning")
            trks = topath(getattr(track, 'path'))
        return trks+grs

class GrFilesIO(TrackIO, _GrFilesIOMixin):
    "Adds an alignment to the tracks per default"
    EXT = _GrFilesIOMixin.EXT

    def __init__(self, *_):
        TrackIO.__init__(self, *_)
        _GrFilesIOMixin.__init__(self, *_)

    def open(self, path:OpenType, _:tuple):
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

    def open(self, path:OpenType, _:tuple):
        path = self._open(path, _)
        if path is None:
            return None

        return ConfigTrackIO.open(self, path, _)

class ConfigMuWellsFilesIO(ConfigTrackIO):
    "Adds an alignment to the tracks per default"
    EXT = ('txt',)

    def __init__(self, ctrl, *_):
        super().__init__(ctrl, *_)
        ctrl.theme.add(MuWellsFilesIO.DEFAULT)
        ctrl.display.observe("tasks", partial(self._onchangedisplay, ctrl, [None]))
        ctrl.theme.observe("tasks", partial(self._onrescale, ctrl))

    @staticmethod
    def _onchangedisplay(ctrl, cur, **_):
        root        = ctrl.display.get('tasks', 'roottask')
        old, cur[:] = cur[:], []
        if root is None or cur == old:
            return

        if MuWellsFilesIO.check(root.path):
            bead  = ctrl.display.get('tasks', 'bead')
            cur   = [root, bead]
            if cur == old:
                return

            track = ctrl.tasks.track(root)
            if bead in getattr(track, 'experimentallength', ()):
                cur = [root, bead]
                model = ctrl.theme.model('tasks')
                ctrl.theme.update(model, **model.rescale(track, bead))

    @staticmethod
    def _onrescale(ctrl, old = None, model = None, **_):
        if 'rescaling' not in old:
            return

        root  = ctrl.display.get("tasks", "roottask")
        instr = getattr(ctrl.tasks.track(root).instrument['type'], 'value', None)
        if instr not in model.rescaling:
            return

        coeff = float(model.rescaling[instr]) / float(old['rescaling'][instr])
        for task in list(ctrl.tasks.tasklist(root))[::-1]:
            cpy = dict(task.zscaled(coeff))
            if cpy:
                ctrl.tasks.updatetask(root, task, **cpy)

    def open(self, path:OpenType, _:tuple):
        "open a LIA file"
        trail = topath(path)
        trks  = tuple(i for i in trail if i.suffix[1:] in TrackIO.EXT)
        lias  = tuple(i for i in trail if i.suffix[1:] == self.EXT[-1])
        if len(trks) + len(lias) < len(trail) or len(trks) > 1 or len(lias) < 1:
            return None

        if len(trks) == 0:
            track = self._ctrl.display.get("tasks", "roottask")
            if track is None:
                raise IOError("IOError: start by opening a track file!", "warning")
            trks = topath(getattr(track, 'path'))

        return super().open(trks+lias, _)

def openmodels(
        openers, task, tasks, ext: str = '**/*.trk', ignore = 'ramp'
) -> List[Tuple[bool, Tuple[Task,...]]]:
    "opens all models"
    if (
            isinstance(task, (str, Path)) and Path(task).is_dir()
            and not any(Path(task).glob("*.cgr"))
            and not any(Path(task).glob("*.gr"))
    ):
        task = {i.stem: str(i) for i in Path(task).glob(ext) if ignore not in i.stem}

    elif (
            isinstance(task, (list, tuple))
            and not any(Path(i).suffix == f'.{GrFilesIO.EXT[-1]}' for i in task)
    ):
        task = {Path(i).stem: str(i) for i in task}

    if isinstance(task, dict):
        models: list = []
        for trk in TracksDict(**cast(dict, task)).values():
            for isarch, mdl in openmodels(openers, trk.path, tasks):
                trk.path = mdl[0].path
                models.append((
                    isarch,
                    (type(mdl[0])(trk, copy = mdl[0].copy),) + tuple(mdl[1:])
                ))
        if len(models) == 0:
            raise IOError(f"Couldn't open: {task}", 'warning')
        return models

    for obj in openers:
        models = obj.open(task, tasks)
        if models is not None:
            return [(isarchive(task), i) for i in models]

    path = getattr(task, 'path', task)
    if path is None or (isinstance(path, (list, tuple))) and len(path) == 0:
        msg  = "Couldn't open track"

    elif isinstance(path, (tuple, list)):
        msg  = f"Couldn't open: {Path(str(path[0])).name}{', ...' if len(path) else ''}"
    else:
        msg  = f"Couldn't open: {Path(str(path)).name}"

    raise IOError(msg, 'warning')

def isarchive(task, archiveext = ('.xlsx', '.ana')) -> bool:
    "whether the argument is an archive path"
    return (
        isinstance(task, (Path, str, tuple, list))
        and any(
            str(task if isinstance(task, (Path, str)) else task[-1]).endswith(i)
            for i in archiveext
        )
    )
