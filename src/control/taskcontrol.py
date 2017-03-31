#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Task controller.

The controller stores:
    - lists of tasks (ProcessorController.model),
    - their associated processors and cache (ProcessorController.data).

It can add/delete/update tasks, emitting the corresponding events
"""
from typing         import (Union, Iterator, Tuple, # pylint: disable=unused-import
                            Optional, Any, List, Iterable, Dict)

from model.task     import Task, RootTask, TaskIsUniqueError
from .event         import Controller, NoEmission
from .processor     import Cache, Processor, run as _runprocessors
from .taskio        import DefaultTaskIO, GrFilesIO, TrackIO

_m_none = type('_m_none', (), {}) # pylint: disable=invalid-name

class ProcessorController:
    "data and model for tasks"
    __slots__ = ('model', 'data')
    def __init__(self):
        self.model   = []         # type: List[Task]
        self.data    = Cache()

    def task(self, task:Union[Task,int,type], noemission = False) -> Task:
        "returns a task"
        tsk = None
        if isinstance(task, Task):
            tsk = task

        elif isinstance(task, int):
            tsk = self.model[task]

        elif isinstance(task, type):
            try:
                tsk = next(i for i in self.model if isinstance(i, task))
            except StopIteration:
                pass

        if tsk is None and noemission:
            raise NoEmission("Missing task")
        return tsk

    def add(self, task, proctype, index = _m_none):
        "adds a task to the list"
        TaskIsUniqueError.verify(task, self.model)
        proc = proctype(task)

        if index is _m_none:
            self.model.append(task)
            self.data .append(proc)
        else:
            self.model.insert(index, task)
            self.data .insert(index, proc)

    def remove(self, task):
        "removes a task from the list"
        task = self.task(task)

        self.model.remove(task)
        self.data .remove(task)

    def update(self, tsk):
        "clears data starting at *tsk*"
        self.data.delCache(tsk)

    def clear(self):
        "clears data starting at *tsk*"
        self.data.delCache()

    def run(self, tsk:Optional[Task] = None, copy = False):
        """
        Iterates through the list up to and including *tsk*.
        Iterates through all if *tsk* is None
        """
        return _runprocessors(self.model, self.data, tsk, copy = copy)

    @classmethod
    def create(cls,
               model     : Iterable[Task],
               processors: 'Union[Dict,Iterable[type],type,None]' = Processor
              ) -> 'ProcessorController':
        "creates a task pair for this model"
        tasks = tuple(model)
        pair  = cls()
        if not isinstance(processors, Dict):
            processors = cls.register(processors)

        for other in tasks:
            pair.add(other, processors[type(other)])
        return pair

    @classmethod
    def register(cls,
                 processor: Union[Iterable[type], Processor, None] = None,
                 cache:     Optional[dict]                         = None
                ) -> 'Dict[type,Any]':
        "registers a task processor"
        if cache is None:
            cache = dict()

        if isinstance(processor, Iterable[Processor]):
            for proc in processor:
                cls.register(proc, cache)
            return cache

        elif processor is None:
            return cache

        if isinstance(processor.tasktype, tuple):
            cache.update(dict.fromkeys(processor.tasktype, processor))
        elif processor.tasktype is not None:
            cache[processor.tasktype] = processor

        for sclass in processor.__subclasses__():
            cls.register(sclass, cache)
        return cache

def create(model     : Iterable[Task],
           processors: 'Union[Dict,Iterable[type],type,None]' = Processor
          ) -> 'ProcessorController':
    "creates a task pair for this model"
    return ProcessorController.create(model, processors)

class TaskController(Controller):
    "Data controller class"
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.__items   = dict() # type: Dict[RootTask, ProcessorController]
        self.__procs   = dict() # type: Dict[type,Any]
        self.__procs   = ProcessorController.register(kwargs.get('processors', Processor))

        self.__openers = kwargs.get("openers", self.__defaultopeners())
        self.__savers  = kwargs.get("savers",  self.__defaultsavers())

    def task(self,
             parent : RootTask,
             task   : Union[Task,int,type],
             noemission = False) -> Task:
        "returns a task"
        return self.__items[parent].task(task, noemission = noemission)

    def track(self, parent : Optional[RootTask]):
        "returns the root cache, i;e. the track"
        if parent not in self.__items:
            return None
        track = self.__items[parent].data[0].cache()
        if track is None:
            self.__items[parent].run(parent) # create cache if needed
            track = self.__items[parent].data[0].cache()
        return track

    def tasks(self, task:Optional[RootTask]) -> 'Iterator[Task]':
        "Returns a data object in memory."
        if task is None:
            return iter(tuple())
        if task is Ellipsis:
            return iter(self.tasks(tsk) for tsk in self.__items.keys())
        return iter(tsk for tsk in self.__items[task].model)

    def cache(self, parent:RootTask, tsk:Optional[Task]):
        "Returns the cache for a given task"
        return self.__items[parent].data.getCache(tsk)

    def run(self, parent:RootTask, tsk:Task, copy = False):
        """
        Iterates through the list up to and including *tsk*.
        Iterates through all if *tsk* is None
        """
        return self.__items[parent].run(tsk, copy = copy)

    @Controller.emit
    def saveTrack(self, path: str) -> None:
        "saves the current model"
        items = [item.model for item in self.__items.values()]
        for obj in self.__savers:
            if obj.close(path, items):
                break

    @Controller.emit
    def openTrack(self,
                  task : 'Union[None,str,RootTask]' = None,
                  model: Iterable[Task]             = tuple()) -> dict:
        "opens a new file"
        tasks = tuple(model)
        if task is None:
            if len(tasks) == 0:
                raise NoEmission("Nothing to do")
            task = tasks[0]

        if not isinstance(task, RootTask):
            for obj in self.__openers:
                models = obj.open(task, tasks)
                if models is not None:
                    break

            for elem in models:
                self.openTrack(elem[0], elem)
            raise NoEmission("Done everything already")

        if len(tasks) == 0:
            tasks = (task,)

        elif tasks[0] is not task:
            raise ValueError("model and root task does'nt coincide")

        self.__items[task] = ProcessorController.create(tasks, self.__procs)
        return dict(controller = self, model = tasks)

    @Controller.emit
    def closeTrack(self, task:RootTask) -> dict:
        "opens a new file"
        old = tuple(self.__items[task].model)
        del self.__items[task]
        return dict(controller = self, task = task, model = old)

    @Controller.emit
    def addTask(self, parent:RootTask, task:Task, index = None) -> dict:
        "opens a new file"
        old = tuple(self.__items[parent].model)
        self.__items[parent].add(task, self.__procs[type(task)], index = index)
        return dict(controller = self, parent = parent, task = task, old = old)

    @Controller.emit
    def updateTask(self, parent:RootTask, task:Union[Task,int,type], **kwargs) -> dict:
        "updates a task"
        tsk = self.task(parent, task, noemission = True)
        old = Controller.updateModel(tsk, **kwargs)
        self.__items[parent].update(tsk)
        return dict(controller = self, parent = parent, task = tsk, old = old)

    @Controller.emit
    def removeTask(self, parent:RootTask, task:Union[Task,int,type]) -> dict:
        "removes a task"
        tsk = self.task(parent, task, noemission = True)
        old = tuple(self.__items[parent].model)
        self.__items[parent].remove(tsk)
        return dict(controller = self, parent = parent, task = tsk, old = old)

    @Controller.emit
    def clearData(self, parent:'Optional[RootTask]' = _m_none) -> dict:
        "clears all data"
        if parent is _m_none:
            self.__items.clear()
        elif parent not in self.__items:
            raise NoEmission('wrong key')
        else:
            self.__items[parent].clear()
        return dict(controller = self, parent = parent)

    @staticmethod
    def __undos__():
        "yields all undoable user actions"
        # pylint: disable=unused-variable
        _1  = None
        def _onOpenTrack(controller = _1, model = _1, **_):
            task = model[0]
            return lambda: controller.closeTrack(task)

        def _onCloseTrack(controller = _1, model = _1, **_):
            return lambda: controller.openTrack(model[0], model)

        def _onAddTask(controller = _1, parent = _1, task = _1, **_):
            return lambda: controller.removeTask(parent, task)

        def _onUpdateTask(controller = _1, parent = _1, task = _1,  old = _1, **_):
            return lambda: controller.updateTask(parent, task, **old)

        def _onRemoveTask(controller = _1, parent = _1, task = _1,  old = _1, **_):
            ind = old.index(task)
            return lambda: controller.addTask(parent, task, ind)

        yield from (fcn for name, fcn in locals().items() if name[:3] == '_on')

    @classmethod
    def __defaultopeners(cls):
        "yields default openers"
        return cls.__defaultsavers() + [GrFilesIO(), TrackIO()]

    @staticmethod
    def __defaultsavers():
        "yields default openers"
        return [cls() for cls in DefaultTaskIO.__subclasses__()]
