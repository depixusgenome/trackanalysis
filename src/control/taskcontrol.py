#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"""
Task controler.

The controler stores:
    - lists of tasks (TaskPair.model),
    - their associated processors and cache (TaskPair.data).

It can add/delete/update tasks, emitting the corresponding events
"""
from typing         import (Union, Iterator, Tuple, # pylint: disable=unused-import
                            Optional, Any, List)

from model.task     import Task, TrackReaderTask, TaskIsUniqueError
from .event         import Controler, NoEmission
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
        self.data.clear()

class TaskControler(Controler):
    u"Data controler class"
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

    @Controler.emit(returns = Controler.outasdict)
    def openTrack(self, task: 'Union[str,TrackReaderTask]', model = tuple()):
        u"opens a new file"
        if isinstance(task, str):
            task = TrackReaderTask(path = task)

        pair  = TaskPair()
        tasks = (model if len(model) else (task,))
        for other in tasks:
            pair.add(other, self._processors[type(other)])

        self._items[task] = pair
        return dict(controler = self, model = tasks)

    @Controler.emit(returns = Controler.outasdict)
    def closeTrack(self, task:TrackReaderTask):
        u"opens a new file"
        old = tuple(self._items[task].model)
        del self._items[task]
        return dict(controler = self, task = task, model = old)

    @Controler.emit(returns = Controler.outasdict)
    def addTask(self, parent:TrackReaderTask, task:Task, index = None):
        u"opens a new file"
        old = tuple(self._items[parent].model)
        self._items[parent].add(task, self._processors[type(task)], index = index)
        return dict(controler = self, parent = parent, task = task, old = old)

    @Controler.emit(returns = Controler.outasdict)
    def updateTask(self, parent:TrackReaderTask, task:Union[Task,int,type], **kwargs):
        u"updates a task"
        tsk = self.task(parent, task, noemission = True)
        old = Controler.updateModel(tsk, **kwargs)
        self._items[parent].update(tsk)
        return dict(controler = self, parent = parent, task = tsk, old = old)

    @Controler.emit(returns = Controler.outasdict)
    def removeTask(self, parent:TrackReaderTask, task:Union[Task,int,type]):
        u"removes a task"
        tsk = self.task(parent, task, noemission = True)
        old = tuple(self._items[parent].model)
        self._items[parent].remove(tsk)
        return dict(controler = self, parent = parent, task = tsk, old = old)

    @Controler.emit
    def clearData(self, parent:'Optional[TrackReaderTask]' = None):
        "clears all data"
        if parent is None:
            self._data.clear()
        else:
            self._data[parent].clear()

    def register(self, processor = None):
        u"registers a task processor"
        if processor is None:
            processor = Processor

        self._processors[processor.tasktype] = processor
        for sclass in processor.__subclasses__():
            self.register(sclass)
