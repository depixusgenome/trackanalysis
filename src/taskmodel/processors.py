#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Task controller.

The controller stores:
    - lists of tasks (ProcessorController.model),
    - their associated processors and cache (ProcessorController.data).

It can add/delete/update tasks, emitting the corresponding events
"""
from typing  import Union, Type, Dict, Optional, List, TYPE_CHECKING
from .       import Task, TaskIsUniqueError

if TYPE_CHECKING:
    from taskcontrol.processor  import Cache, Processor  # noqa

appendtask = type('appendtask', (), {})  # pylint: disable=invalid-name


class TaskCacheList:
    "data and model for tasks"
    model: List[Task]
    data:  'Cache'
    copy:  bool
    __slots__ = ('model', 'data', 'copy')

    def __init__(self, copy = True):
        self.model: List[Task] = []
        self.copy              = copy

    def __contains__(self, itm):
        return self.task(itm) in self.model

    def task(self, task:Union[Type[Task],int], noemission = False) -> Optional[Task]:
        "returns a task"
        if isinstance(task, Task):
            return task

        if isinstance(task, int):
            return self.model[task]

        tsk = None
        if isinstance(task, type):
            try:
                tsk = next((i for i in self.model if isinstance(i, task)), None)
            except StopIteration:
                pass

        if tsk is None and noemission:
            raise KeyError("Missing task")
        return tsk

    def add(self, task, proctype, index = appendtask):
        "adds a task to the list"
        TaskIsUniqueError.verify(task, self.model)
        proc = proctype(task)

        if index is appendtask:
            self.model.append(task)
            self.data.append(proc)
            return []
        self.model.insert(index, task)
        return self.data .insert(index, proc)

    def remove(self, task):
        "removes a task from the list"
        tsk = self.task(task)
        if tsk in self.model:
            ind = self.model.index(tsk)
            self.model.pop(ind)
            return self.data.remove(ind)
        return None

    def update(self, tsk):
        "clears data starting at *tsk*"
        return self.data.delcache(tsk)

    def cleancopy(self) -> 'TaskCacheList':
        "returns a cache with only the processors"
        cpy = self.__class__(copy = self.copy)
        cpy.model = self.model
        cpy.data  = self.data.cleancopy()
        return cpy

    def clear(self):
        "clears data starting at *tsk*"
        self.data.delcache()

    def keepupto(self, tsk:Task = None, included = True) -> 'TaskCacheList':
        "Returns a processor for a given root and range"
        ind         = None if tsk is None else self.data.index(tsk)
        other       = type(self)(copy = self.copy)
        other.model = self.model[:None if ind is None else ind+(1 if included else 0)]
        other.data  = self.data.keepupto(ind, included)
        return other

    def run(self, tsk:Task = None, copy = None, pool = None):
        """
        Iterates through the list up to and including *tsk*.
        Iterates through all if *tsk* is None
        """
        raise NotImplementedError("implemented in the controller module")

    @classmethod
    def create(cls, *models: Task, processors = None) -> 'TaskCacheList':
        """
        Creates a ProcessorController containing a list of task-processor pairs.

        Parameters:
        -----------
        models: Tuple[Task]
            a sequence of tasks
        processors: Dict[Type[Task], Processor], Iterable[Type[Processor]] or None
            this argument allows defining which processors to use for implementing
            the provided tasks
        """
        raise NotImplementedError("implemented in the controller module")

    @classmethod
    def register(
            cls,
            processor = None,
            cache     = None,
            force     = False,
    ) -> Dict[Type[Task], Type['Processor']]:
        "registers a task processor"
        raise NotImplementedError("implemented in the controller module")
