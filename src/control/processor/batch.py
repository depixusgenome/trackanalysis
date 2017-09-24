#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Batch creator basics"
from typing             import (TypeVar, Iterator, Union, Iterable, Sequence,
                                Type, cast)
from pathlib            import Path
from copy               import deepcopy, copy as shallowcopy
from itertools          import chain
from functools          import partial

from utils              import initdefaults, update
from data.views         import TrackView
from data.trackio       import PATHTYPES, PATHTYPE

from model.task         import RootTask, Task, Level
from .base              import Processor

class BatchTemplate(Iterable):
    "Template of tasks to run"
    def __init__(self, **_):
        super().__init__()

    def config(self) -> dict:
        "returns a copy of the dictionnary"
        return deepcopy(self.__dict__)

    def activated(self, aobj:Union[str,Task]) -> bool:
        "Wether the task will be called"
        obj = getattr(self, aobj) if isinstance(aobj, str) else aobj
        for i in self.__iter__():
            if i is obj:
                return True
        return False

    def __iter__(self) -> Iterator[Task]:
        raise NotImplementedError()

class PathIO:
    "Paths (as regex) on which to run"
    track:     PATHTYPES = ''
    reporting: PATHTYPE  = None
    @initdefaults(frozenset(locals()))
    def __init__(self, **kwa):
        pass

class BatchTask(RootTask):
    """
    Constructs a list of tasks depending on a template and paths.
    """
    levelin      = Level.project
    levelou      = Level.peak
    paths:    Sequence[PathIO] = []
    template: BatchTemplate    = None
    @initdefaults(frozenset(locals()))
    def __init__(self, **kwa):
        super().__init__(**kwa)

    @staticmethod
    def pathtype() -> type:
        "the type of paths"
        return PathIO

    @classmethod
    def templatetype(cls) -> type:
        "the type of template"
        return type(cls.template)

    @staticmethod
    def reporttype() -> type:
        "the type of reports"
        raise NotImplementedError()

    def addpaths(self, **kwa):
        "appends a PathIO to the list"
        self.paths.append(self.pathtype()(**kwa))

BTaskType = TypeVar('BTaskType', bound = BatchTask)
class BatchProcessor(Processor[BTaskType]):
    "Constructs a list of tasks depending on a template and paths."
    @staticmethod
    def create(mdl: Sequence[Task], **kwa) -> Iterator:
        "creates a specific model for each path"
        from ..taskcontrol import create
        return create(tuple(mdl)).run(**kwa)

    @classmethod
    def models(cls, *paths, template = None, **kwa) -> Iterator[Sequence[Task]]:
        "iterates through all instanciated models"
        tsk = cast(Type[BatchTask], cls.tasktype)
        if template is None:
            template = next((i for i in paths if isinstance(i, tsk.templatetype())), None)
            paths    = tuple(i for i in paths if not isinstance(i, tsk.templatetype()))

        if len(paths) == 0:
            return

        if isinstance(paths[0], (tuple, list)) and len(paths) == 1:
            paths = tuple(paths[0])

        pathtype = tsk.pathtype()
        paths    = tuple(cls.path(pathtype, i, **kwa) for i in paths)

        if template is None:
            template = tsk.templatetype()(**kwa)
        elif len(kwa):
            template = update(deepcopy(template), **kwa)

        yield from(cls.model(i, template) for i in paths)

    @classmethod
    def reports(cls, *paths, template = None, pool = None, **kwa) -> Iterator[TrackView]:
        "creates TrackViews"
        mdls = cls.models(paths, template = template, **kwa)
        yield from chain.from_iterable(cls.create(i, pool = pool) for i in mdls)

    @classmethod
    def path(cls, pathtype, path, **kwa):
        "creates a path using provided arguments"
        if isinstance(path, dict):
            return pathtype(**path, **kwa)

        elif isinstance(path, pathtype):
            return update(shallowcopy(path), **kwa)

        elif isinstance(path, (tuple, str, Path)):
            return pathtype(track = path, **kwa)

        else:
            raise TypeError('Could not create {} using {}'.format(pathtype, path))

    @classmethod
    def model(cls, paths: PathIO, modl: BatchTemplate) -> Sequence[Task]:
        "creates a specific model for each path"
        raise NotImplementedError()

    def run(self, args):
        "updates frames"
        fcn   = partial(self.reports, *self.task.paths, pool = args.pool,
                        **self.task.template.config())
        args.apply(fcn, levels = self.levels)
