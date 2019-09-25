#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Controller for most plots and views"
import pickle
from typing                 import (Tuple, Optional, Iterator, Union, Any,
                                    Callable, Dict, Type, ClassVar,
                                    TYPE_CHECKING, cast)
from copy                   import copy as shallowcopy

from taskmodel              import RootTask, Task
from taskmodel.application  import ConfigurationDescriptor, TasksDisplay, TasksConfig
from utils                  import NoArgs
from utils.inspection       import diffobj
from .processor             import Processor
from .processor.cache       import CacheReplacement
from .taskcontrol           import ProcessorController

if TYPE_CHECKING:
    # pylint: disable=unused-import
    from data.views          import TrackView        # noqa
    from data.track          import Track            # noqa
    from taskapp.maincontrol import SuperController  # noqa

class PlotModelAccess:
    "Default plot model"
    _ctrl: 'SuperController'

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

    def addto(self, ctrl):
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

class _TDDescriptor:
    _name: str

    def __set_name__(self, _, name):
        self._name = name

    def __get__(self, inst, tpe):
        return (
            self if inst is None else getattr(getattr(inst, '_tasksdisplay'), self._name)
        )

class TaskPlotModelAccess(PlotModelAccess):
    "Contains all access to model items likely to be set by user actions"
    def __init__(self):
        self._tasksconfig  = TasksConfig()
        self._tasksdisplay = TasksDisplay()
        self._defaulttasks = TasksConfig()

    roottask = cast(Optional[RootTask], _TDDescriptor())
    tasklist = cast(Iterator[Task],     _TDDescriptor())
    bead     = cast(Optional[int],      _TDDescriptor())

    @property
    def rawtrack(self) -> Optional['Track']:
        "return the raw track, not undersampled"
        return self._tasksdisplay.track

    @property
    def track(self) -> Optional['Track']:
        "return the potentiallly undersampled track"
        ctrl  = self.processors()
        return None if ctrl is None else  next(iter(ctrl.run(copy = True))).track

    @property
    def instrument(self) -> str:
        "the current instrument type"
        track = self.rawtrack
        return (
            self._tasksdisplay.instrument if track is None else
            track.instrument['type'].name
        )

    @property
    def instrumentdim(self) -> Optional[str]:
        "the current instrument type"
        track = self.rawtrack
        return 'µm' if track is None else track.instrument['dimension']

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
        if self.roottask is None:
            return None

        check = tuple(i.check for i in self.__dict__.values() if isinstance(i, TaskAccess))
        good  = next((j for j in tuple(self.tasklist)[::-1] if any(i(j) for i in check)), None)
        return self._tasksdisplay.processors(good) if good else None

    def statehash(self, root = NoArgs, task = NoArgs):
        "returns a tag specific to the current state"
        lst = tuple(
            self._tasksdisplay.tasklist if root is NoArgs else
            self._ctrl.tasks.tasklist(root)
        )

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

    def runbead(self) -> Optional['TrackView']:
        "returns a TrackView to be displayed"
        ctrl  = self.processors()
        return None if ctrl is None else  next(iter(ctrl.run(copy = True)))

    def runcontext(
            self,
            *processors: Processor,
            ctrl: Optional[ProcessorController] = None,
            copy: bool                          = True
    ) -> ReplaceProcessors:
        "returns a ReplaceProcessors context from which a trackview can be obtains"
        return ReplaceProcessors(ctrl if ctrl else self.processors(), *processors, copy = copy)

    def addtodoc(self, _):
        "adds items to the doc"

    def swapmodels(self, ctrl) -> bool:
        "swap models with those in the controller"
        if ctrl is getattr(self, '_ctrl', ''):
            return False
        self._ctrl         = ctrl
        self._tasksconfig  = ctrl.theme.swapmodels(self._tasksconfig)
        self._defaulttasks = ctrl.theme.model(self._tasksconfig, defaults = True)
        self._tasksdisplay = ctrl.display.swapmodels(self._tasksdisplay)
        for i in self.__dict__.values():
            if callable(getattr(i, 'swapmodels', None)):
                i.swapmodels(ctrl)
        return True

    def observe(self, ctrl):
        "observe models in the controller"
        for i in self.__dict__.values():
            if callable(getattr(i, 'observe', None)):
                i.observe(ctrl)

    def addto(self, ctrl):
        "add to the controller"
        if self.swapmodels(ctrl):
            self.observe(ctrl)

    def _updatedisplay(self, mdl, **kwa):
        self._ctrl.display.update(mdl, **kwa)

    def _updatetheme(self, mdl, **kwa):
        self._ctrl.theme.update(mdl, **kwa)

class _TMDescriptor:
    _name: str

    def __set_name__(self, _, name):
        self._name = name

    def __get__(self, inst, tpe):
        return (
            self if inst is None else getattr(getattr(inst, '_tasksmodel'), self._name)
        )

class TaskAccess:
    "access to tasks"
    tasktype:   ClassVar[Type[Task]]
    attrs:      ClassVar[Tuple[Tuple[str, Any],...]]
    side:       ClassVar[int]
    configname: ClassVar[str]

    def __init__(self, model: TaskPlotModelAccess):
        self._tasksmodel = model

    def swapmodels(self, ctrl):
        "swap models for those in the controller"
        for i, j  in self.__dict__.items():
            if i != '_tasksmodel' and callable(getattr(j, 'swapmodels', None)):
                j.swapmodels(ctrl)

    def __init_subclass__(cls,
                          tasktype:   Type[Task]               = Task,
                          attrs:      Optional[Dict[str, Any]] = None,
                          side:       str                      = 'LEFT',
                          configname: str                      = '') -> None:
        if tasktype is Task:
            raise KeyError(f"missing tasktype in class signature: {cls}")
        cls.attrs      = () if attrs is None else tuple(attrs.items())  # type: ignore
        cls.side       = 0 if side == 'LEFT' else 1
        cls.tasktype   = tasktype
        cls.configname = ConfigurationDescriptor.defaulttaskname(configname, tasktype)

    roottask      = cast(Optional[RootTask], _TDDescriptor())
    tasklist      = cast(Iterator[Task],     _TDDescriptor())
    bead          = cast(Optional[int],      _TDDescriptor())
    instrument    = cast(str,                _TMDescriptor())
    instrumentdim = cast(str,                _TMDescriptor())
    rawtrack      = cast(Optional['Track'],  _TMDescriptor())
    track         = cast(Optional['Track'],  _TMDescriptor())

    def processors(self, task = None) -> Optional[ProcessorController]:
        "returns a tuple (dataitem, bead) to be displayed"
        task = self.task if task is None else task
        return None if task is None else self._tasksdisplay.processors(task)

    @property
    def defaultconfigtask(self) -> Task:
        "returns the config task"
        mdl  = getattr(self._defaulttasks, self.instrument)
        resc = self._tasksconfig.rescaling.get(self.instrument, None)
        if resc:
            return mdl[self.configname].rescale(float(resc))
        return mdl[self.configname]

    @property
    def configtask(self) -> Task:
        "returns the config task"
        return getattr(self._tasksconfig, self.instrument)[self.configname]

    @configtask.setter
    def configtask(self, values: Union[Task, Dict[str,Task]]):
        "returns the config task"
        kwa = diffobj(self.configtask, values) if isinstance(values, Task) else values
        kwa = self._configattributes(kwa)
        if kwa:
            instr                = self.instrument
            cnf                  = dict(getattr(self._tasksconfig, instr))
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
        return self._tasksdisplay.cache(self.task)

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
    def _defaulttasks(self):
        return getattr(self._tasksmodel, '_defaulttasks')

    def _updatedisplay(self, mdl, **kwa):
        getattr(self._tasksmodel, '_updatedisplay')(mdl, **kwa)

    def _updatetheme(self, mdl, **kwa):
        getattr(self._tasksmodel, '_updatetheme')(mdl, **kwa)

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
