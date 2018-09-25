#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Deals with global information"
from typing             import (Dict, Optional, List, Iterator, Type, Iterable,
                                Callable, Any, TYPE_CHECKING)
from copy               import deepcopy
from utils              import initdefaults
from utils.configobject import ConfigObject
from .base              import Task, RootTask
from .order             import TASK_ORDER, taskorder
if TYPE_CHECKING:
    # pylint: disable=unused-import
    from data.track          import Track
    from control.taskcontrol import ProcessorController

DEFAULT_TASKS: Dict[str, Task] = {}

class TasksConfig(ConfigObject):
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
    name                         = "tasks"
    bead:     Optional[int]      = None
    roottask: Optional[RootTask] = None

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

class TaskIOTheme(ConfigObject):
    """
    Info used when opening track files
    """
    name = "tasks.io"
    tasks:      List[str] = []
    inputs:     List[str] = ['anastore.control.ConfigAnaIO',
                             'control.taskio.ConfigGrFilesIO',
                             'control.taskio.ConfigTrackIO']
    outputs:    List[str] = ['anastore.control.ConfigAnaIO']
    processors: List[str] = []
    clear                 = True
    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        pass

    @property
    def inputtypes(self):
        "return loading objects"
        return [self.__import(itm) for itm in self.inputs]

    @property
    def outputtypes(self):
        "return output objects"
        return [self.__import(itm) for itm in self.outputs]

    @property
    def processortypes(self):
        "return processor objects"
        return [self.__import(itm) for itm in self.processors]

    def setup(self, tasks = None, ioopen = None, iosave = None):
        "creates a new object using the current one and proposed changes"
        cpy = deepcopy(self)
        if tasks is not None:
            cpy.tasks = list(tasks)

        for name, vals in (('inputs', ioopen), ('outputs', iosave)):
            if vals is None:
                continue

            old = getattr(cpy, name)
            new = []
            for i in vals:
                if isinstance(i, (str, int)):
                    new.append(old[i] if isinstance(i, int) else i)
                elif isinstance(i, slice) or i is Ellipsis:
                    new.extend(old if i is Ellipsis else old[i])
            setattr(cpy, name, new)
        return cpy

    @staticmethod
    def __import(name):
        if not isinstance(name, str):
            return name
        modname, clsname = name[:name.rfind('.')], name[name.rfind('.')+1:]
        return getattr(__import__(modname, fromlist = [clsname]), clsname)

class TasksModel:
    "tasks related stuff"
    def __init__(self):
        self.config  = TasksConfig()
        self.display = TasksDisplay()

    def addto(self, ctrl, noerase = True):
        """
        adds the current obj to the controller
        """
        self.config  = ctrl.theme  .add(self.config,  noerase)
        self.display = ctrl.display.add(self.display, noerase)
