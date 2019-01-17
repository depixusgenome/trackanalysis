#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Controller for most plots and views"
import pickle
from typing                 import (Tuple, Optional, Iterator, Union, Any,
                                    Callable, Dict, Type, ClassVar,
                                    TYPE_CHECKING, cast)
from copy                   import copy as shallowcopy

from control.decentralized  import Indirection
from data.track             import Track
from data.views             import TrackView
from data.views             import BEADKEY
from taskmodel              import RootTask, Task
from taskmodel.application  import ConfigurationDescriptor, TasksModel
from utils                  import NoArgs
from utils.inspection       import diffobj
from .processor             import Processor
from .processor.cache       import CacheReplacement
from .taskcontrol           import ProcessorController

if TYPE_CHECKING:
    # pylint: disable=unused-import
    from taskapp.taskcontrol import SuperController

class PlotModelAccess:
    "Default plot model"
    def __init__(self, model:Union['SuperController', 'PlotModelAccess']) -> None:
        self._model = model
        self._ctrl  = getattr(model, 'ctrl', model)

    @property
    def ctrl(self):
        "return the controller"
        return self._ctrl

    def clear(self):
        "clears the model's cache"

    @staticmethod
    def reset() -> bool:
        "resets the model"
        return False

    @property
    def themename(self) -> str:
        "return the theme name"
        return self._ctrl.theme.get("main", "themename", "dark")

    def addto(self, ctrl, noerase = False):
        "add to controller"

class ReplaceProcessors(CacheReplacement):
    """
    Context for replacing processors but keeping their cache
    """
    def __init__(self, ctrl, *options: Processor, copy = None) -> None:
        if isinstance(ctrl, TaskPlotModelAccess):
            ctrl = ctrl.processors()

        opt = cast(Tuple[Type[Processor],...], options)
        super().__init__(ctrl.data if ctrl else None, *opt)
        self.ctrl = ctrl
        self.copy = copy

    def __enter__(self):
        if self.ctrl is None:
            return None

        data = super().__enter__()
        if data is not self.ctrl.data:
            ctrl      = shallowcopy(self.ctrl)
            ctrl.data = data
        else:
            ctrl = self.ctrl
        return ctrl if self.copy is None else next(iter(ctrl.run(copy = self.copy)))

class TaskPlotModelAccess(PlotModelAccess):
    "Contains all access to model items likely to be set by user actions"
    _tasksconfig  = Indirection()
    _tasksdisplay = Indirection()
    def __init__(self, model:Union['SuperController', 'PlotModelAccess']) -> None:
        super().__init__(model)
        mdl = TasksModel()
        self._tasksconfig               = mdl.config
        self._tasksdisplay              = mdl.display

    @property
    def roottask(self) -> Optional[RootTask]:
        "returns the current track"
        return self._tasksdisplay.roottask

    @property
    def tasklist(self) -> Iterator[Task]:
        "return the tasklist associated to the root task"
        return self._tasksdisplay.tasklist(self._ctrl)

    @property
    def track(self) -> Optional[Track]:
        "returns the current track"
        return self._tasksdisplay.track(self._ctrl)

    @property
    def bead(self) -> Optional[BEADKEY]:
        "returns the current bead number"
        return self._tasksdisplay.bead

    @property
    def instrument(self) -> str:
        "the current instrument type"
        if self.roottask is None:
            return self._ctrl.theme.get("tasks", "instrument")
        return self._ctrl.tasks.instrumenttype(self.roottask)

    def impacts(self, root:RootTask, task:Task) -> bool:
        "returns whether changing this tasks affects the model output"
        if root is not self.roottask:
            return False

        order = tuple(self._tasksconfig.taskorder)
        order = order[order.index(type(task)):]
        return any(val.tasktype in order for val in self.__dict__.values()
                   if isinstance(val, TaskAccess))

    def processors(self) -> Optional[ProcessorController]:
        "returns a tuple (dataitem, bead) to be displayed"
        if self.track is None:
            return None

        check = tuple(i.check for i in self.__dict__.values() if isinstance(i, TaskAccess))
        good  = next((j for j in tuple(self.tasklist)[::-1] if any(i(j) for i in check)), None)
        return self._tasksdisplay.processors(self._ctrl, good) if good else None

    def statehash(self, root = NoArgs, task = NoArgs):
        "returns a tag specific to the current state"
        lst = tuple(self._ctrl.tasks.tasklist(self.roottask if root is NoArgs else root))
        if task is NoArgs:
            check = tuple(
                i.check for i in self.__dict__.values() if isinstance(i, TaskAccess)
            )

            for i in range(len(lst), -1, -1):
                if any(fcn(lst[i]) for fcn in check):
                    lst = lst[:i+1]
                    break

        elif task in lst:
            lst = lst[:lst.index(task)+1]
        return pickle.dumps(lst)

    def runbead(self) -> Optional[TrackView]:
        "returns a TrackView to be displayed"
        ctrl  = self.processors()
        return None if ctrl is None else  next(iter(ctrl.run(copy = True)))

    def runcontext(self, *processors: Processor, copy = True) -> ReplaceProcessors:
        "returns a ReplaceProcessors context from which a trackview can be obtains"
        return ReplaceProcessors(self.processors(), *processors, copy = copy)

    def addtodoc(self, _):
        "adds items to the doc"

class TaskAccess:
    "access to tasks"
    tasktype:   ClassVar[Type[Task]]
    attrs:      ClassVar[Tuple[Tuple[str, Any],...]]
    side:       ClassVar[int]
    configname: ClassVar[str]
    def __init__(self, model: TaskPlotModelAccess):
        self._tasksmodel = model

    def __init_subclass__(cls,
                          tasktype:   Type[Task]               = Task,
                          attrs:      Optional[Dict[str, Any]] = None,
                          side:       str                      = 'LEFT',
                          configname: str                      = '') -> None:
        if tasktype is Task:
            raise KeyError(f"missing tasktype in class signature: {cls}")
        cls.attrs      = () if attrs is None else tuple(attrs.items()) # type: ignore
        cls.side       = 0 if side == 'LEFT' else 1
        cls.tasktype   = tasktype
        cls.configname = ConfigurationDescriptor.defaulttaskname(configname, tasktype)

    @property
    def roottask(self) -> Optional[RootTask]:
        "returns the current track"
        return self._tasksmodel.roottask

    @property
    def tasklist(self) -> Iterator[Task]:
        "return the tasklist associated to the root task"
        return self._tasksmodel.tasklist

    @property
    def track(self) -> Optional[Track]:
        "returns the current track"
        return self._tasksmodel.track

    @property
    def bead(self) -> Optional[BEADKEY]:
        "returns the current bead number"
        return self._tasksmodel.bead

    @property
    def instrument(self) -> str:
        "the current instrument type"
        if self.roottask is None:
            return self._ctrl.theme.get("tasks", "instrument")
        return self._ctrl.tasks.instrumenttype(self.roottask)

    def processors(self) -> Optional[ProcessorController]:
        "returns a tuple (dataitem, bead) to be displayed"
        task = self.task
        return None if task is None else self._tasksdisplay.processors(self._ctrl, task)

    @property
    def defaultconfigtask(self) -> Task:
        "returns the config task"
        mdl = self._ctrl.theme.get("tasks", self.instrument, defaultmodel = True)
        return mdl[self.configname]

    @property
    def configtask(self) -> Task:
        "returns the config task"
        return self._ctrl.theme.get("tasks", self.instrument)[self.configname]

    @configtask.setter
    def configtask(self, values: Union[Task, Dict[str,Task]]):
        "returns the config task"
        kwa = diffobj(self.configtask, values) if isinstance(values, Task) else values
        kwa = self._configattributes(kwa)
        if kwa:
            instr                = self.instrument
            cnf                  = dict(self._ctrl.theme.get("tasks", instr))
            cnf[self.configname] = self.__deepcopy(cnf[self.configname], kwa)
            self._ctrl.theme.update("tasks", **{instr: cnf})

    @property
    def task(self) -> Optional[Task]:
        "returns the task if it exists"
        task = self._task
        return None if getattr(task, 'disabled', True) else task

    @property
    def index(self) -> Optional[Task]:
        "returns the index the new task should have"
        return self._tasksconfig.defaulttaskindex(self.tasklist, self.tasktype, self.side)

    @property
    def cache(self) -> Callable[[],Any]:
        "returns the processor's cache if it exists"
        return self._tasksdisplay.cache(self._ctrl, self.task)

    @cache.setter
    def cache(self, value):
        "sets the processor's cache if the task exists"
        ctrl = self.processors()
        if ctrl is not None:
            ctrl.data.setcache(self.task, value)

    @property
    def processor(self) -> Optional[Processor]:
        "returns the processor if it exists"
        if self.task is None:
            return None
        return next((t for t in cast(Iterator[Processor], self.tasklist) if self.check(t)),
                    None)

    def update(self, **kwa):
        "adds/updates the task"
        root = self.roottask
        if root is None:
            return
        task = self._task
        ctrl = self._ctrl.tasks
        if kwa.get('disabled', False):
            if task is None:
                return
            ctrl.removetask(root, task)
            kwa = {'disabled': True}

        elif task is None:
            kwa['disabled'] = False
            item = self.__deepcopy(self.configtask, kwa)
            ctrl.addtask(root, item, index = self.index)
        else:
            kwa['disabled'] = False
            ctrl.updatetask(root, task, **kwa)

        self.configtask = kwa

    def check(self, task, parent = NoArgs) -> bool:
        "wether this controller deals with this task"
        return self._check(task, parent) and not task.disabled

    def statehash(self, root = NoArgs, task = NoArgs):
        "returns a tag specific to the current state"
        return self._tasksmodel.statehash(root, self.task if task is NoArgs else task)

    @property
    def _ctrl(self):
        return self._tasksmodel.ctrl

    @property
    def _tasksdisplay(self):
        return getattr(self._tasksmodel, '_tasksdisplay')

    @property
    def _tasksconfig(self):
        return getattr(self._tasksmodel, '_tasksconfig')

    @property
    def _task(self) -> Optional[Task]:
        "returns the task if it exists"
        return next((t for t in self.tasklist if self._check(t)), None)

    @staticmethod
    def _configattributes(kwa):
        return kwa

    def _check(self, task, parent = NoArgs) -> bool:
        "wether this controller deals with this task"
        return (isinstance(task, self.tasktype)
                and (parent is NoArgs or parent is self.roottask)
                and all(getattr(task, i) == j for i, j in self.attrs))

    @staticmethod
    def __deepcopy(task, kwa):
        cnf = task.__getstate__() if hasattr(task, '__getstate__') else dict(task.__dict__)
        cnf.update(kwa)

        out = type(task)(**cnf)
        return out