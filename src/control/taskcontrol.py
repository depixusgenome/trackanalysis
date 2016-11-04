#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"""
Task controller.

The controller stores:
    - lists of tasks (TaskPair.model),
    - their associated processors and cache (TaskPair.data).

It can add/delete/update tasks, emitting the corresponding events
"""
from typing         import (Union, Iterator, Tuple, # pylint: disable=unused-import
                            Optional, Any, List)

from model.task     import Task, TrackReaderTask, TaskIsUniqueError
from anastore       import load as _anaopen, dump as _anasave
from .event         import Controller, NoEmission
from .processor     import Cache, Processor, run as _runprocessors

class TaskPair:
    u"data and model for tasks"
    __slots__ = ('model', 'data')
    def __init__(self):
        self.model = []         # type: List[Task]
        self.data  = Cache()

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
            raise NoEmission()
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

class TaskController(Controller):
    u"Data controller class"
    def __init__(self):
        super().__init__()
        self._items      = dict() # type: Dict[TrackReaderTask, TaskPair]
        self._processors = dict() # type: Dict[Task,Any]
        self.register()

    def task(self,
             parent : TrackReaderTask,
             task   : Union[Task,int,type],
             noemission = False) -> Task:
        u"returns a task"
        return self._items[parent].task(task, noemission = noemission)

    @property
    def tasktree(self) -> 'Iterator[Iterator[Task]]':
        u"Returns a data object in memory."
        return iter(self.tasks(tsk) for tsk in self._items.keys())

    def tasks(self, task:TrackReaderTask) -> 'Iterator[Task]':
        u"Returns a data object in memory."
        return iter(tsk for tsk in self._items[task].model)

    def cache(self, parent:TrackReaderTask, tsk:Optional[Task]):
        u"Returns the cache for a given task"
        return self._items[parent].data.getCache(tsk)

    def run(self, parent:TrackReaderTask, tsk:Optional[Task]):
        u"""
        Iterates through the list up to and including *tsk*.
        Iterates through all if *tsk* is None
        """
        return _runprocessors(self._items[parent].data, tsk)

    @Controller.emit
    def saveTrack(self, path: str):
        u"saves the current model"
        _anasave([item.model for item in self._items.values()], path)

    @Controller.emit(returns = Controller.outasdict)
    def openTrack(self, task: 'Union[str,TrackReaderTask]', model = tuple()):
        u"opens a new file"
        if isinstance(task, str):
            if len(model):
                raise NotImplementedError()

            models = _anaopen(task)
            if models is None:
                model = tuple()
                task  = TrackReaderTask(path = task)
            elif len(models) == 1:
                model = models[0]
                task  = model [0]
            else:
                for model in models:
                    self.openTrack(model[0], model)
                raise NoEmission("Done everything already")

        pair  = TaskPair()
        tasks = (model if len(model) else (task,))
        for other in tasks:
            pair.add(other, self._processors[type(other)])

        self._items[task] = pair
        return dict(controller = self, model = tasks)

    @Controller.emit(returns = Controller.outasdict)
    def closeTrack(self, task:TrackReaderTask):
        u"opens a new file"
        old = tuple(self._items[task].model)
        del self._items[task]
        return dict(controller = self, task = task, model = old)

    @Controller.emit(returns = Controller.outasdict)
    def addTask(self, parent:TrackReaderTask, task:Task, index = None):
        u"opens a new file"
        old = tuple(self._items[parent].model)
        self._items[parent].add(task, self._processors[type(task)], index = index)
        return dict(controller = self, parent = parent, task = task, old = old)

    @Controller.emit(returns = Controller.outasdict)
    def updateTask(self, parent:TrackReaderTask, task:Union[Task,int,type], **kwargs):
        u"updates a task"
        tsk = self.task(parent, task, noemission = True)
        old = Controller.updateModel(tsk, **kwargs)
        self._items[parent].update(tsk)
        return dict(controller = self, parent = parent, task = tsk, old = old)

    @Controller.emit(returns = Controller.outasdict)
    def removeTask(self, parent:TrackReaderTask, task:Union[Task,int,type]):
        u"removes a task"
        tsk = self.task(parent, task, noemission = True)
        old = tuple(self._items[parent].model)
        self._items[parent].remove(tsk)
        return dict(controller = self, parent = parent, task = tsk, old = old)

    @Controller.emit
    def clearData(self, parent:'Optional[TrackReaderTask]' = None):
        "clears all data"
        if parent is None:
            self._items.clear()
        else:
            self._items[parent].clear()

    def register(self, processor = None):
        u"registers a task processor"
        if processor is None:
            processor = Processor

        self._processors[processor.tasktype] = processor
        for sclass in processor.__subclasses__():
            self.register(sclass)
