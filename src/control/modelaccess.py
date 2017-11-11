#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Controller for most plots and views"
from typing          import (Tuple, Optional, # pylint: disable =unused-import
                             Iterator, List, Union, Any, Callable, Dict,
                             TypeVar, Callable)
from copy            import copy as shallowcopy
from enum            import Enum
from functools       import wraps

from signalfilter    import rawprecision
from model.task      import RootTask, Task, taskorder, TASK_ORDER
from model.globals   import PROPS
from data.track      import Track
from data.views      import BEADKEY
from utils           import NoArgs, updatecopy, updatedeepcopy
from .processor      import Processor
from .taskcontrol    import ProcessorController
from .globalscontrol import GlobalsAccess
from .event          import Controller

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
        self._ctrl   = getattr(model, '_ctrl', model)

    def clear(self):
        "clears the model's cache"

    def create(self, _):
        "creates the model"

    @staticmethod
    def reset() -> bool:
        "resets the model"
        return False

class TaskPlotModelAccess(PlotModelAccess):
    "Contains all access to model items likely to be set by user actions"
    def __init__(self, *args, **kwa):
        super().__init__(*args, **kwa)
        cnf = self.config.root.precision
        cnf.defaults = {'min': 1e-4,
                        'max': 1e-2,
                        'title': ("Bead {bead} has "
                                  +"{min:.4f} ≮ σ[HF] = {val:.4f} ≮ {max:.4f}")}

    @property
    def bead(self) -> Optional[BEADKEY]:
        "returns the current bead number"
        bead = self.project.bead.get()
        if bead is None:
            track = self.track
            if track is not None:
                return next(iter(track.beadsonly.keys()))
        return bead

    def checkbead(self, throwerr = True) -> bool:
        "checks that the bead is correct"
        prec = rawprecision(self.track, self.bead)
        cnf  = self.config.precision
        if not cnf.max.get() > prec > cnf.min.get():
            msg = cnf.title.format(bead = self.bead,
                                   min  = cnf.min.get(),
                                   val  = prec,
                                   max  = cnf.max.get())
            if throwerr:
                raise ValueError(msg, 'warning')
            else:
                self.project.root.message = (msg, 'warning')
            return True
        return False

    def clear(self):
        u"updates the model when a new track is loaded"
        PROPS.BeadProperty.clear(self)

    @property
    def roottask(self) -> Optional[RootTask]:
        "returns the current root task"
        return self.project.track.get()

    @property
    def currenttask(self) -> Optional[Task]:
        "returns the current task"
        return self.project.task.get()

    @property
    def track(self) -> Optional[Track]:
        "returns the current track"
        return self._ctrl.track(self.roottask)

    def impacts(self, root:RootTask, task:Task) -> bool:
        "returns whether changing this tasks affects the model output"
        if root is not self.roottask:
            return False

        order = tuple(taskorder(self.config.tasks.order.get()))
        order = order[order.index(type(task)):]
        return any(val.tasktype in order for val in self.__dict__.values()
                   if isinstance(val, TaskAccess))

    def checktask(self, root:RootTask, task:Task) -> bool:
        "checks wether a task belongs to the model"
        if not any(val.check(task) for val in self.__dict__.values()
                   if isinstance(val, TaskAccess)):
            return False

        return root is self.roottask

    def processors(self, *procs) -> Optional[ProcessorController]:
        "returns a tuple (dataitem, bead) to be displayed"
        track = self.track
        if track is None:
            return None

        root = self.roottask
        for task in tuple(self._ctrl.tasks(root))[::-1]:
            if not self.checktask(root, task):
                continue

            ctrl = self._ctrl.processors(root, task)
            data = ctrl.data.replace(*procs)
            if data is not ctrl.data:
                ctrl      = shallowcopy(ctrl)
                ctrl.data = data
            return ctrl
        return None

    def runbead(self, *procs):
        "returns a tuple (dataitem, bead) to be displayed"
        ctrl  = self.processors(*procs)
        ibead = self.bead
        if ctrl is None:
            return None

        return next(iter(ctrl.run(copy = True)))[ibead, ...]

    def observetasks(self, *args, **kwa):
        "observes the provided task"
        def _check(parent = None, task = None, **_):
            if self.project.state.get() is PlotState.active:
                return self.checktask(parent, task)
            return False
        self._ctrl.observe(*args, argstest = _check, **kwa)

    def wrapobserver(self, fcn):
        "wraps an observing function"
        state = self.project.state
        @wraps(fcn)
        def _wrapped(*args, **kwargs):
            if state.get() is PlotState.active:
                fcn(*args, **kwargs)
            elif state.get() is PlotState.disabled:
                state.set(PlotState.outofdate)
        return _wrapped

    def observeprop(self, *args):
        "observe an attribute set through props"
        fcn   = self.wrapobserver(next(i for i in args if callable(i)))
        attrs = tuple(i for i in args if isinstance(i, str))
        assert len(attrs) + 1 == len(args)

        keys = dict() # type: Dict[str, List[str]]
        cls  = type(self)
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

class TaskAccess(TaskPlotModelAccess):
    "access to tasks"
    def __init__(self, ctrl: PlotModelAccess, tasktype: type, **kwa) -> None:
        super().__init__(ctrl)
        self.attrs      = kwa.get('attrs', {})
        self.tasktype   = tasktype
        self.side       = (0  if kwa.get('side', 'LEFT') == 'LEFT' else 1)
        self.permanent  = kwa.get('permanent', False)
        self.configname = kwa.get('configname',
                                  tasktype.__name__.lower()[:-len('Task')])

        # pylint: disable=not-callable
        self.config.root.tasks.order.default = list(TASK_ORDER)

        cur = self.config.root.tasks.get(self.configname, default = None)
        assert cur is None or isinstance(cur, tasktype)
        self.config.root.tasks[self.configname].default = tasktype(**self.attrs)

    @property
    def configtask(self) -> Task:
        "returns the config task"
        return self.config.root.tasks[self.configname]

    def remove(self):
        "removes the task"
        task = self.task
        if task is not None:
            if self.permanent:
                return self._ctrl.updateTask(self.roottask, task, disabled = True)
            else:
                self._ctrl.removeTask(self.roottask, task)

            kwa = self._configattributes({'disabled': True})
            if len(kwa):
                cnf = self.configtask
                cnf.set(updatecopy(cnf.get(), **kwa))

    def update(self, **kwa):
        "adds/updates the task"
        root = self.roottask
        task = self._task
        cnf  = self.configtask

        kwa.setdefault('disabled', False)
        if task is None:
            item = updatedeepcopy(cnf.get(), **kwa)
            self._ctrl.addTask(root, item, index = self.index)
        else:
            self._ctrl.updateTask(root, task, **kwa)

        kwa = self._configattributes(kwa)
        if len(kwa):
            cnf = self.configtask
            cnf.set(updatecopy(cnf.get(), **kwa))

    @property
    def _task(self) -> Optional[Task]:
        "returns the task if it exists"
        return next((t for t in self._ctrl.tasks(self.roottask) if self._check(t)), None)

    @property
    def task(self) -> Optional[Task]:
        "returns the task if it exists"
        task = self._task
        return None if getattr(task, 'disabled', True) else task

    @property
    def processor(self) -> Optional[Processor]:
        "returns the processor if it exists"
        task = self.task
        if task is None:
            return None
        return next((t for t in self._ctrl.tasks(self.roottask) if self.check(t)), None)

    @property
    def cache(self) -> Callable[[],Any]:
        "returns the processor's cache if it exists"
        task = self.task
        if task is None:
            return lambda: None
        return self._ctrl.cache(self.roottask, task)

    def _check(self, task, parent = NoArgs) -> bool:
        "wether this controller deals with this task"
        return (isinstance(task, self.tasktype)
                and (parent is NoArgs or parent is self.roottask)
                and all(getattr(task, i) == j for i, j in self.attrs.items()))

    def check(self, task, parent = NoArgs) -> bool:
        "wether this controller deals with this task"
        return self._check(task, parent) and not task.disabled

    @property
    def index(self) -> Optional[Task]:
        "returns the index the new task should have"
        return self._ctrl.defaulttaskindex(self.roottask, self.tasktype, self.side)

    def observe(self, *args, **kwa):
        "observes the provided task"
        check = lambda parent = None, task = None, **_: self.check(task, parent)
        self._ctrl.observe(*args, argstest = check, **kwa)

    @staticmethod
    def _configattributes(kwa):
        return kwa
