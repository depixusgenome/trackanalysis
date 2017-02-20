#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"""
Task controller.

The controller stores:
    - lists of tasks (ProcessorController.model),
    - their associated processors and cache (ProcessorController.data).

It can add/delete/update tasks, emitting the corresponding events
"""
from typing         import (Union, Iterator, Tuple, # pylint: disable=unused-import
                            Optional, Any, List, Iterable, Dict)

from model.task     import Task, RootTask, TrackReaderTask, TaskIsUniqueError
from .event         import Controller, NoEmission
from .processor     import Cache, Processor, run as _runprocessors
from .              import FileIO

class ProcessorController:
    u"data and model for tasks"
    __slots__ = ('model', 'data')
    def __init__(self):
        self.model   = []         # type: List[Task]
        self.data    = Cache()

    def task(self, task:Union[Task,int,type], noemission = False) -> Task:
        u"returns a task"
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

    def add(self, task, proctype, index = None):
        u"adds a task to the list"
        TaskIsUniqueError.verify(task, self.model)
        proc = proctype(task)

        if index is None:
            self.model.append(task)
            self.data .append(proc)
        else:
            self.model.insert(index, task)
            self.data .insert(index, proc)

    def remove(self, task):
        u"removes a task from the list"
        task = self.task(task)

        self.model.remove(task)
        self.data .remove(task)

    def update(self, tsk):
        u"clears data starting at *tsk*"
        self.data.delCache(tsk)

    def clear(self):
        u"clears data starting at *tsk*"
        self.data.delCache()

    def run(self, tsk:Optional[Task] = None):
        u"""
        Iterates through the list up to and including *tsk*.
        Iterates through all if *tsk* is None
        """
        return _runprocessors(self.data, tsk)

    @classmethod
    def create(cls,
               model     : Iterable[Task],
               processors: 'Union[Dict,Iterable[type],type,None]' = Processor
              ) -> 'ProcessorController':
        u"creates a task pair for this model"
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
        u"registers a task processor"
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
    u"creates a task pair for this model"
    return ProcessorController.create(model, processors)

class TaskController(Controller):
    u"Data controller class"
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.__items   = dict() # type: Dict[RootTask, ProcessorController]
        self.__procs   = dict() # type: Dict[type,Any]
        self.__procs   = ProcessorController.register(kwargs.get('processors', Processor))
        self.__openers = kwargs.get("openers", self.defaultopener)
        self.__savers  = kwargs.get("savers",  self.defaultsaver)

    @staticmethod
    def defaultopener():
        u"yields default openers"
        for cls in FileIO.__subclasses__():
            yield cls().open

    @staticmethod
    def defaultsaver():
        u"yields default openers"
        for cls in FileIO.__subclasses__():
            yield cls().save

    def task(self,
             parent : RootTask,
             task   : Union[Task,int,type],
             noemission = False) -> Task:
        u"returns a task"
        return self.__items[parent].task(task, noemission = noemission)

    @property
    def tasktree(self) -> 'Iterator[Iterator[Task]]':
        u"Returns a data object in memory."
        return iter(self.tasks(tsk) for tsk in self.__items.keys())

    def tasks(self, task:RootTask) -> 'Iterator[Task]':
        u"Returns a data object in memory."
        return iter(tsk for tsk in self.__items[task].model)

    def cache(self, parent:RootTask, tsk:Optional[Task]):
        u"Returns the cache for a given task"
        return self.__items[parent].data.getCache(tsk)

    def run(self, parent:RootTask, tsk:Task):
        u"""
        Iterates through the list up to and including *tsk*.
        Iterates through all if *tsk* is None
        """
        return self.__items[parent].run(tsk)

    @Controller.emit
    def saveTrack(self, path: str) -> None:
        u"saves the current model"
        items = [item.model for item in self.__items.values()]
        for closing in self.__savers():
            if closing(path, items):
                break

    @Controller.emit
    def openTrack(self,
                  task : 'Union[None,str,RootTask]' = None,
                  model: Iterable[Task]             = tuple()) -> dict:
        u"opens a new file"
        tasks = tuple(model)
        if task is None:
            if len(tasks) == 0:
                raise NoEmission("Nothing to do")
            task = tasks[0]

        if not isinstance(task, RootTask):
            for opening in self.__openers():
                models = opening(task, tasks)
                if models is not None:
                    break
            else:
                if len(tasks):
                    raise NotImplementedError()
                models = [(TrackReaderTask(path = task),)]

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
        u"opens a new file"
        old = tuple(self.__items[task].model)
        del self.__items[task]
        return dict(controller = self, task = task, model = old)

    @Controller.emit
    def addTask(self, parent:RootTask, task:Task, index = None) -> dict:
        u"opens a new file"
        old = tuple(self.__items[parent].model)
        self.__items[parent].add(task, self.__procs[type(task)], index = index)
        return dict(controller = self, parent = parent, task = task, old = old)

    @Controller.emit
    def updateTask(self, parent:RootTask, task:Union[Task,int,type], **kwargs) -> dict:
        u"updates a task"
        tsk = self.task(parent, task, noemission = True)
        old = Controller.updateModel(tsk, **kwargs)
        self.__items[parent].update(tsk)
        return dict(controller = self, parent = parent, task = tsk, old = old)

    @Controller.emit
    def removeTask(self, parent:RootTask, task:Union[Task,int,type]) -> dict:
        u"removes a task"
        tsk = self.task(parent, task, noemission = True)
        old = tuple(self.__items[parent].model)
        self.__items[parent].remove(tsk)
        return dict(controller = self, parent = parent, task = tsk, old = old)

    @Controller.emit
    def clearData(self, parent:'Optional[RootTask]' = None) -> dict:
        "clears all data"
        if parent is None:
            self.__items.clear()
        else:
            self.__items[parent].clear()
        return dict(controller = self, parent = parent)

    @staticmethod
    def __undos__():
        u"yields all undoable user actions"
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

        def _onDeleteTask(controller = _1, parent = _1, task = _1,  old = _1, **_):
            ind = old.index(task)
            return lambda: controller.addTask(parent, task, ind)

        yield from (fcn for name, fcn in locals().items() if name[:3] == '_on')
