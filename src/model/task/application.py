#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Deals with global information"
from typing             import (Dict, Optional, List, Iterator, Type, Iterable,
                                Callable, Any, TYPE_CHECKING)
from utils              import initdefaults
from utils.configobject import ConfigObject
from .base              import Task, RootTask
from .order             import TASK_ORDER, taskorder
if TYPE_CHECKING:
    # pylint: disable=unused-import
    from data.track          import Track
    from control.taskcontrol import ProcessorController

DEFAULT_TASKS: Dict[str, Task] = {}

class TasksTheme(ConfigObject):
    """
    permanent globals on tasks
    """
    name                   = "tasks"
    tasks: Dict[str, Task] = DEFAULT_TASKS
    order: List[str]       = list(TASK_ORDER)

    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        pass

    @property
    def taskorder(self) -> Iterator[Type[Task]]:
        "return the task order"
        return taskorder(self.order)

    def defaulttaskindex(self, tasklist:Iterable[Task], task:Type[Task], side = 0) -> int:
        "returns the default task index"
        if not isinstance(task, type):
            task = type(task)
        order    = tuple(self.taskorder)
        previous = order[:order.index(task)+side]

        curr     = tuple(tasklist)
        for i, tsk in enumerate(curr[1:]):
            if not isinstance(tsk, previous):
                return i+1
        return len(curr)

class TasksDisplay(ConfigObject):
    """
    runtime globals on tasks
    """
    name = "tasks"
    bead:     int       = None
    roottask: RootTask  = None

    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        pass

    def track(self, ctrl) -> Optional['Track']:
        "return the track associated to the root task"
        return None if self.roottask is None else ctrl.tasks.track(self.roottask)

    def tasklist(self, ctrl) -> Iterator[Task]:
        "return the tasklist associated to the root task"
        return ctrl.tasks.tasklist(self.roottask) if self.roottask else iter(())

    def processors(self, ctrl, upto:Task = None) -> Optional['ProcessorController']:
        "return the tasklist associated to the root task"
        return ctrl.tasks.processors(self.roottask, upto) if self.roottask else None

    def cache(self, ctrl, task) -> Callable[[], Any]:
        "returns the processor's cache if it exists"
        return ctrl.tasks.cache(self.roottask, task) if task else lambda: None

class TasksModel:
    "tasks related stuff"
    theme   = TasksTheme()
    display = TasksDisplay()

    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        pass
