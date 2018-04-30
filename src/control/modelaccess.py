#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Controller for most plots and views"
from typing                 import (Tuple, Optional, Iterator, List, Union, Any,
                                    Callable, Dict, Type, ClassVar, cast)
from copy                   import copy as shallowcopy
from enum                   import Enum
from functools              import wraps

from model.task             import RootTask, Task
from model.task.application import DEFAULT_TASKS, TasksDisplay, TasksTheme, TasksModel
from model.globals          import PROPS
from data.track             import Track
from data.views             import TrackView
from data.views             import BEADKEY
from utils                  import NoArgs, updatecopy, updatedeepcopy
from .processor             import Processor
from .processor.cache       import CacheReplacement
from .taskcontrol           import ProcessorController
from .globalscontrol        import GlobalsAccess
from .event                 import Controller

class PlotState(Enum):
    "plot state"
    active       = 'active'
    abouttoreset = 'abouttoreset'
    resetting    = 'resetting'
    disabled     = 'disabled'
    outofdate    = 'outofdate'

class PlotModelAccess(GlobalsAccess):
    "Default plot model"
    def __init__(self, model:Union[Controller, 'PlotModelAccess'], key = None) -> None:
        super().__init__(model, key)
        self._ctrl = getattr(model, '_ctrl', model)

    def clear(self):
        "clears the model's cache"

    @staticmethod
    def reset() -> bool:
        "resets the model"
        return False

    @property
    def themename(self) -> str:
        "return the theme name"
        ctrl = getattr(self._ctrl, 'theme', None)
        mdl  = getattr(ctrl, 'model', lambda _: None)('main')
        return getattr(mdl, 'themename', 'dark')

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
    def __init__(self, model:Union[Controller, 'PlotModelAccess'], key = None) -> None:
        super().__init__(model, key)
        self._tasksmodel = TasksModel(theme   = TasksTheme  (name = key),
                                      display = TasksDisplay(name = key))

    def settaskmodel(self, ctrl, name):
        "set _tasksmodel to same as main"
        if name in ctrl.theme:
            self._tasksmodel = TasksModel(theme   = ctrl.theme.model(name),
                                          display = ctrl.display.model(name))
        else:
            self._tasksmodel.theme  .name = name
            self._tasksmodel.display.name = name
            ctrl.theme  .add(self._tasksmodel.theme)
            ctrl.display.add(self._tasksmodel.display)

        for inst in self.__dict__.values():
            if isinstance(inst, TaskPlotModelAccess):
                inst.settaskmodel(ctrl, name)

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
                return next(iter(track.beadsonly.keys()))
        return bead

    def impacts(self, root:RootTask, task:Task) -> bool:
        "returns whether changing this tasks affects the model output"
        if root is not self.roottask:
            return False

        order = tuple(self._tasksmodel.theme.taskorder)
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

    def observeprop(self, *args):
        "observe an attribute set through props"
        fcn   = self.__wrapobserver(next(i for i in args if callable(i)))
        attrs = tuple(i for i in args if isinstance(i, str))
        assert len(attrs) + 1 == len(args)

        keys: Dict[str, List[str]] = dict()
        cls                        = type(self)
        for attr in attrs:
            if '.' in attr:
                for key in ('config.root.', 'project.root.', 'project.', 'config.'):
                    if attr.startswith(key):
                        keys.setdefault(key[:-1], []).append(attr[len(key):])
            else:
                prop = getattr(cls, attr)
                for obs in prop.OBSERVERS:
                    keys.setdefault(obs, []).append(prop.key)

        for key, items in keys.items():
            val = self
            for attr in key.split('.'):
                val = getattr(val, attr)
            val.observe(*items, fcn) # pylint: disable=no-member

    def clear(self):
        u"updates the model when a new track is loaded"
        PROPS.BeadProperty.clear(self)

    def __wrapobserver(self, fcn):
        "wraps an observing function"
        state = self.project.state
        @wraps(fcn)
        def _wrapped(*args, **kwargs):
            if state.get() is PlotState.active:
                fcn(*args, **kwargs)
            elif state.get() is PlotState.disabled:
                state.set(PlotState.outofdate)
        return _wrapped

class TaskAccess(TaskPlotModelAccess):
    "access to tasks"
    tasktype:   ClassVar[Type[Task]]
    attrs:      ClassVar[Tuple[Tuple[str, Any],...]]
    side:       ClassVar[int]
    configname: ClassVar[str]
    def __init__(self, ctrl: PlotModelAccess, **_) -> None:
        super().__init__(ctrl)
        assert isinstance(self.configtask, self.tasktype)

    def __init_subclass__(cls, **kwa):
        cls.side       = 0 if kwa.pop('side', 'LEFT') == 'LEFT' else 1
        cls.tasktype   = cast(Type[Task], kwa.pop('tasktype'))
        cls.configname = kwa.pop('configname',
                                 cls.tasktype.__name__.lower()[:-len('Task')])
        cls.attrs      = tuple(kwa.items())

        inst = cls.tasktype(**dict(cls.attrs))
        name = cls.configname
        assert name not in DEFAULT_TASKS or inst == DEFAULT_TASKS[name]
        DEFAULT_TASKS[name] = inst

    @property
    def configtask(self) -> Task:
        "returns the config task"
        return self._tasksmodel.theme.tasks[self.configname]

    @property
    def task(self) -> Optional[Task]:
        "returns the task if it exists"
        task = self._task
        return None if getattr(task, 'disabled', True) else task

    @property
    def index(self) -> Optional[Task]:
        "returns the index the new task should have"
        theme = self._tasksmodel.theme
        return theme.defaulttaskindex(self.tasklist, self.tasktype, self.side)

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
    def remove(self):
        "removes the task"
        task = self.task
        if task is not None:
            self._ctrl.tasks.removetask(self.roottask, task)

            kwa = self._configattributes({'disabled': True})
            if len(kwa):
                cnf = self.configtask
                cnf.set(updatecopy(cnf.get(), **kwa))
        return None

    def update(self, **kwa):
        "adds/updates the task"
        root = self.roottask
        task = self._task
        cnf  = self.configtask

        kwa.setdefault('disabled', False)
        if task is None:
            item = updatedeepcopy(cnf.get(), **kwa)
            self._ctrl.tasks.addtask(root, item, index = self.index)
        else:
            self._ctrl.tasks.updatetask(root, task, **kwa)

        kwa = self._configattributes(kwa)
        if len(kwa):
            cnf = self.configtask
            cnf.set(updatecopy(cnf.get(), **kwa))

    def check(self, task, parent = NoArgs) -> bool:
        "wether this controller deals with this task"
        return self._check(task, parent) and not task.disabled

    def observe(self, *args, **kwa):
        "observes the provided task"
        check = lambda parent = None, task = None, **_: self.check(task, parent)
        self._ctrl.tasks.observe(*args, argstest = check, **kwa)

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
