#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Deals with global information"
from enum               import Enum
from typing             import (Dict, Optional, List, Iterator, Type, Iterable,
                                Callable, Any, ClassVar, TYPE_CHECKING, cast)
from copy               import deepcopy
from utils              import initdefaults
from utils.configobject import ConfigObject
from .base              import Task, RootTask
from .dataframe         import DataFrameTask
from .order             import TASK_ORDER, taskorder
from .track             import (CycleSamplingTask, TrackReaderTask,
                                DataSelectionTask, CycleCreatorTask)
from ..                 import InstrumentType
if TYPE_CHECKING:
    # pylint: disable=unused-import
    from data.track          import Track
    from control.taskcontrol import ProcessorController

Configuration  = Dict[str, Task]
Configurations = Dict[str, Configuration]

class ConfigurationDescriptor:
    """ configurations """
    _Type: ClassVar[Type[Enum]] = InstrumentType
    _instr: str
    def __set_name__(self, _, name):
        self._instr = self._Type(name)

    def __get__(self, inst, owner):
        if inst is None:
            return {i:j for i, j in self._instr.__dict__.items() if i[0] != '_'}
        return inst.__dict__[self._instr.name]

    def __set__(self, inst, val):
        good = dict(val)
        good.update({i: deepcopy(j)
                     for i, j in self.__get__(None, None).items()
                     if i not in good})
        inst.__dict__[self._instr.name] = good
        return good

    @classmethod
    def setupdefaulttask(cls, tasktype: Type[Task], name: str = '', **kwa) -> str:
        "add task to the instruments"
        instruments = {cls._Type(i): kwa.pop(i) for i in set(cls._Type.__members__) & set(kwa)}
        name        = name if name else tasktype.__name__.lower()[:-len('Task')]

        for instr in cls._Type.__members__.values():
            itm = tasktype(**dict(kwa, **instruments.get(instr, {})))
            assert itm == getattr(instr, name, itm)
            setattr(instr, name, itm)
        return name

    @classmethod
    def defaulttaskname(cls, name:str, tasktype: Type[Task]):
        "verify that a task default has been defined"
        name = name if name else tasktype.__name__.lower()[:-len('Task')]
        for i in cls._Type.__members__.values():
            assert isinstance(getattr(i, name, None), tasktype)
        return name

class InstrumentDescriptor:
    """ tasks """
    def __get__(self, inst, owner):
        return (InstrumentType.picotwist.name if inst is None else
                inst.__dict__["instrument"])

    def __set__(self, inst, val):
        inst.__dict__['instrument'] = InstrumentType(val).name
        return inst.__dict__['instrument']

class TasksConfig(ConfigObject):
    """
    permanent globals on tasks
    """
    name                       = "tasks"
    instrument: str            = InstrumentType.picotwist.name
    picotwist:  Configuration  = cast(Configuration, ConfigurationDescriptor())
    sdi:        Configuration  = cast(Configuration, ConfigurationDescriptor())
    order:      List[str]      = list(TASK_ORDER)

    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        pass

    def __getitem__(self, key):
        return getattr(self, InstrumentType(key).name)

    @staticmethod
    def __config__(cmap):
        "simplify a config map"
        for i in {'picotwist', 'sdi'} & set(cmap.maps[0]):
            left            = cmap.maps[1][i]
            cmap.maps[0][i] = {j: k for j, k in cmap.maps[0][i].items() if left[j] != k}

    @property
    def tasks(self) -> Configuration:
        "return the current task list"
        return getattr(self, self.instrument)

    @tasks.setter
    def tasks(self, values):
        "return the current task list"
        return setattr(self, self.instrument, values)

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

def setupdefaulttask(tasktype: Type[Task], name :str = '', **kwa) -> str:
    "add task to the instruments"
    return ConfigurationDescriptor.setupdefaulttask(tasktype, name, **kwa)

setupdefaulttask(CycleSamplingTask)
setupdefaulttask(TrackReaderTask)
setupdefaulttask(DataSelectionTask)
setupdefaulttask(CycleCreatorTask)
setupdefaulttask(DataFrameTask)
