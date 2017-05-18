#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Batch creator basics"
from typing        import (Optional,  # pylint: disable=unused-import
                           Iterator, Union, Iterable, Sequence)
from copy          import deepcopy
from itertools     import chain
from functools     import partial

from utils         import initdefaults, update
from data.trackio  import PATHTYPES, PATHTYPE # pylint: disable=unused-import

from model.task    import RootTask, Task, Level
from .base         import Processor

class BatchTemplate(Iterable):
    "Template of tasks to run"
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
    track     = ''    # type: PATHTYPES
    reporting = None  # type: Optional[PATHTYPE]
    @initdefaults(frozenset(locals()))
    def __init__(self, **kwa):
        pass

class BatchTask(RootTask):
    """
    Constructs a list of tasks depending on a template and paths.
    """
    levelin      = Level.project
    levelou      = Level.peak
    paths        = []           # type: Sequence[PathIO]
    template     = None         # type: BatchTemplate
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

class BatchProcessor(Processor):
    "Constructs a list of tasks depending on a template and paths."
    @staticmethod
    def create(mdl: Sequence[Task], **kwa) -> Iterator:
        "creates a specific model for each path"
        from ..taskcontrol import create
        return create(mdl).run(**kwa)

    @classmethod
    def models(cls, *paths, template = None, **kwa) -> Iterator[Sequence[Task]]:
        "iterates through all instanciated models"
        tsk = cls.tasktype
        if template is None:
            template = next((i for i in paths if isinstance(i, tsk.templatetype())), None)
            paths    = tuple(i for i in paths if not isinstance(i, tsk.templatetype()))

        if len(paths) == 0:
            return

        if isinstance(paths[0], (tuple, list)) and len(paths) == 1:
            paths = tuple(paths[0])

        paths = tuple(i if isinstance(i, tsk.pathtype()) else tsk.pathtype()(**i)
                      for i in paths)

        if template is None:
            template = tsk.templatetype()(**kwa)
        elif len(kwa):
            template = update(deepcopy(template), **kwa)

        yield from(cls.model(i, template) for i in paths)

    @classmethod
    def reports(cls, *paths, template = None, pool = None, **kwa) -> Iterator[Sequence[Task]]:
        "creates and runs models"
        mdls = cls.models(paths, template = template, **kwa)
        yield from chain.from_iterable(cls.create(i, pool = pool) for i in mdls)

    @classmethod
    def model(cls, paths: PathIO, modl: BatchTemplate) -> Sequence[Task]:
        "creates a specific model for each path"
        raise NotImplementedError()

    def run(self, args):
        fcn   = partial(self.reports, *self.task.paths, pool = args.pool,
                        **self.task.template.config())
        args.apply(fcn, levels = self.levels)
