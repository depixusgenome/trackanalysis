#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Controller for most plots and views"
from typing                 import (Tuple, Optional, Iterator, Union, Any,
                                    Callable, Dict, Type, ClassVar, cast)
from copy                   import copy as shallowcopy

from model.task             import RootTask, Task
from model.task.application import ConfigurationsDescriptor, TasksModel
from data.track             import Track
from data.views             import TrackView
from data.views             import BEADKEY
from utils                  import NoArgs
from utils.inspection       import diffobj
from .processor             import Processor
from .processor.cache       import CacheReplacement
from .taskcontrol           import ProcessorController
from .event                 import Controller

class PlotModelAccess:
    "Default plot model"
    def __init__(self, model:Union[Controller, 'PlotModelAccess']) -> None:
        self._model = model
        self._ctrl  = getattr(model, '_ctrl', model)

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

    def addto(self, ctrl, name = "tasks", noerase = False):
        "add to controller"
        pass

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
    def __init__(self, model:Union[Controller, 'PlotModelAccess']) -> None:
        super().__init__(model)
        self._tasksmodel = TasksModel()

    def addto(self, ctrl, name = "tasks", noerase = False):
        "set _tasksmodel to same as main"
        lst = (('display', 'display'), ('config', 'theme'))
        for i, j in lst:
            itm = getattr(self._tasksmodel , i)
            itm.name = name
            setattr(self._tasksmodel, i, getattr(ctrl, j).add(itm, noerase))

        objs = [(i, getattr(ctrl, j).model(getattr(self._tasksmodel, i))) for i, j in lst]
        done = set()
        itms = {self}
        while len(itms):
            cur = itms.pop()
            for i, j in objs:
                setattr(getattr(cur, '_tasksmodel'), i, j)
            done.add(cur)
            itms.update(i for i in cur.__dict__.values()
                        if isinstance(i, TaskPlotModelAccess) and i not in done)

    @property
    def roottask(self) -> Optional[RootTask]:
        "returns the current track"
        return self._tasksmodel.display.roottask

    @property
    def tasklist(self) -> Iterator[Task]:
        "return the tasklist associated to the root task"
        return self._tasksmodel.display.tasklist(self._ctrl)

    @property
    def track(self) -> Optional[Track]:
        "returns the current track"
        return self._tasksmodel.display.track(self._ctrl)

    @property
    def bead(self) -> Optional[BEADKEY]:
        "returns the current bead number"
        bead = self._tasksmodel.display.bead
        if bead is None:
            track = self.track
            if track is not None:
                return next(iter(track.beads.keys()))
        return bead

    def impacts(self, root:RootTask, task:Task) -> bool:
        "returns whether changing this tasks affects the model output"
        if root is not self.roottask:
            return False

        order = tuple(self._tasksmodel.config.taskorder)
        order = order[order.index(type(task)):]
        return any(val.tasktype in order for val in self.__dict__.values()
                   if isinstance(val, TaskAccess))

    def processors(self) -> Optional[ProcessorController]:
        "returns a tuple (dataitem, bead) to be displayed"
        if self.track is None:
            return None

        check = tuple(i.check for i in self.__dict__.values() if isinstance(i, TaskAccess))
        good  = next((j for j in tuple(self.tasklist)[::-1] if any(i(j) for i in check)), None)
        return self._tasksmodel.display.processors(self._ctrl, good) if good else None

    def runbead(self) -> Optional[TrackView]:
        "returns a TrackView to be displayed"
        ctrl  = self.processors()
        return None if ctrl is None else  next(iter(ctrl.run(copy = True)))

    def runcontext(self, *processors: Processor, copy = True) -> ReplaceProcessors:
        "returns a ReplaceProcessors context from which a trackview can be obtains"
        return ReplaceProcessors(self, *processors, copy = copy)

    def addtodoc(self, _):
        "adds items to the doc"

class TaskAccess(TaskPlotModelAccess):
    "access to tasks"
    tasktype:   ClassVar[Type[Task]]
    attrs:      ClassVar[Tuple[Tuple[str, Any],...]]
    side:       ClassVar[int]
    configname: ClassVar[str]
    def __init_subclass__(cls,
                          tasktype:   Type[Task]               = Task,
                          attrs:      Optional[Dict[str, Any]] = None,
                          side:       str                      = 'LEFT',
                          configname: str                      = ''):
        if tasktype is Task:
            raise KeyError(f"missing tasktype in class signature: {cls}")
        cls.attrs      = () if attrs is None else tuple(attrs.items()) # type: ignore
        cls.side       = 0 if side == 'LEFT' else 1
        cls.tasktype   = tasktype
        cls.configname = ConfigurationsDescriptor.defaulttaskname(configname, tasktype)

    @staticmethod
    def __deepcopy(task, kwa):
        cnf = task.__getstate__() if hasattr(task, '__getstate__') else dict(task.__dict__)
        cnf.update(kwa)

        out = type(task)(**cnf)
        return out

    @property
    def instrument(self) -> str:
        "the current instrument type"
        if self.roottask is None:
            return self._ctrl.theme.get("tasks", "instrument")
        return self._ctrl.tasks.instrumenttype(self.roottask)

    @property
    def defaultconfigtask(self) -> Task:
        "returns the config task"
        return (self._ctrl.theme.get("tasks", "configurations", {}, True)
                .get(self.instrument, {})
                .get(self.configname, None))

    @property
    def configtask(self) -> Task:
        "returns the config task"
        return self._tasksmodel.config.configurations[self.instrument][self.configname]

    @configtask.setter
    def configtask(self, values: Union[Task, Dict[str,Task]]):
        "returns the config task"
        instr = self.instrument
        task  = self._tasksmodel.config.configurations[instr][self.configname]

        kwa   = diffobj(task, values) if isinstance(values, Task) else values
        kwa   = self._configattributes(kwa)
        if not kwa:
            return

        cnf = dict(self._ctrl.theme.get("tasks", "configurations", {}))
        cnf[instr][self.configname] = self.__deepcopy(cnf[instr][self.configname], kwa)
        self._ctrl.theme.update("tasks", configurations = cnf)

    @property
    def task(self) -> Optional[Task]:
        "returns the task if it exists"
        task = self._task
        return None if getattr(task, 'disabled', True) else task

    @property
    def index(self) -> Optional[Task]:
        "returns the index the new task should have"
        return self._tasksmodel.config.defaulttaskindex(self.tasklist, self.tasktype, self.side)

    @property
    def cache(self) -> Callable[[],Any]:
        "returns the processor's cache if it exists"
        return self._tasksmodel.display.cache(self._ctrl, self.task)

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

        if kwa.get('disabled', False):
            if task is None:
                return
            self._ctrl.tasks.removetask(root, task)
            kwa = {'disabled': True}

        elif task is None:
            kwa['disabled'] = False
            item = self.__deepcopy(self.configtask, kwa)
            self._ctrl.tasks.addtask(root, item, index = self.index)
        else:
            kwa['disabled'] = False
            self._ctrl.tasks.updatetask(root, task, **kwa)

        self.configtask = kwa

    def check(self, task, parent = NoArgs) -> bool:
        "wether this controller deals with this task"
        return self._check(task, parent) and not task.disabled

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
