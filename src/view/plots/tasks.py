#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Utils for dealing with the JS side of the view"
from typing            import (Tuple, Optional, # pylint: disable =unused-import
                               Iterator, List, Union, Any, Callable, Dict,
                               TYPE_CHECKING)

from model.task        import RootTask, Task, taskorder, TASK_ORDER
from model.globals     import ConfigProperty, ConfigRootProperty, BeadProperty
from data.track        import Track
from utils             import NoArgs, updatecopy, updatedeepcopy
from control.processor import Processor
from .base             import PlotModelAccess, PlotCreator

class TaskPlotModelAccess(PlotModelAccess):
    "Contains all access to model items likely to be set by user actions"
    @property
    def bead(self) -> Optional[int]:
        "returns the current bead number"
        bead = self.project.bead.get()
        if bead is None:
            track = self.track
            if track is not None:
                return next(iter(track.beadsonly.keys()))
        return bead

    def clear(self):
        u"updates the model when a new track is loaded"
        BeadProperty.clear(self)

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

    def checktask(self, root, task):
        "checks wether a task belongs to the model"
        if not any(val.check(task) for val in self.__dict__.values()
                   if isinstance(val, TaskAccess)):
            return False

        return root is self.roottask

    def runbead(self):
        "returns a tuple (dataitem, bead) to be displayed"
        track = self.track
        if track is None:
            return None

        root  = self.roottask
        ibead = self.bead

        for task in tuple(self._ctrl.tasks(root))[::-1]:
            if self.checktask(root, task):
                beads = next(iter(self._ctrl.run(root, task, copy = True)))
                return beads[ibead,...]

        return track.cycles[ibead,...]

    def observetasks(self, *args, **kwa):
        "observes the provided task"
        def _check(parent = None, task = None, **_):
            return self.checktask(parent, task)
        self._ctrl.observe(*args, argstest = _check, **kwa)

    def observeprop(self, *args):
        "observe an attribute set through props"
        fcn   = next (i for i in args if callable(i))
        attrs = tuple(i for i in args if isinstance(i, str))
        assert len(attrs) + 1 == len(args)

        keys = dict() # type: Dict[str, List[str]]
        cls  = type(self)
        for attr in attrs:
            prop = getattr(cls, attr)
            for obs in prop.OBSERVERS:
                keys.setdefault(obs, []).append(prop.key)

        for key, items in keys.items():
            getattr(self, key).observe(items, fcn)

    class props: # pylint: disable=invalid-name
        "access to property builders"
        configroot = ConfigRootProperty
        config     = ConfigProperty
        bead       = BeadProperty

class TaskAccess(TaskPlotModelAccess):
    "access to tasks"
    def __init__(self, ctrl: PlotModelAccess, tasktype: type, **kwa) -> None:
        super().__init__(ctrl)
        self.attrs     = kwa.get('attrs', {})
        self.tasktype  = tasktype
        self.side      = (0  if kwa.get('side', 'LEFT') == 'LEFT' else 1)

        # pylint: disable=not-callable
        self.configroot.tasks.order.default            = TASK_ORDER
        self.configroot.tasks[self.configname].default = tasktype(**self.attrs)

    @property
    def configname(self) -> str:
        "returns the config name"
        return self.__class__.__name__.lower()[:-len('Access')]

    @property
    def configtask(self) -> Task:
        "returns the config task"
        return self.configroot.tasks[self.configname]

    def remove(self):
        "removes the task"
        task = self.task
        if task is not None:
            self._ctrl.removeTask(self.roottask, task)

            cnf = self.configtask
            cnf.set(updatecopy(cnf.get(), disabled = True))

    def update(self, **kwa):
        "removes the task"
        root = self.roottask
        task = self.task
        cnf  = self.configtask
        if task is None:
            kwa.setdefault('disabled', False)
            item = updatedeepcopy(cnf.get(), **kwa)
            self._ctrl.addTask(root, item, index = self.index)
        else:
            self._ctrl.updateTask(root, task, **kwa)
        cnf.set(updatecopy(cnf.get(), **kwa))

    @property
    def task(self) -> Optional[Task]:
        "returns the task if it exists"
        return next((t for t in self._ctrl.tasks(self.roottask) if self.check(t)), None)

    @property
    def processor(self) -> Optional[Processor]:
        "returns the task if it exists"
        task = self.task
        if task is None:
            return None
        return next((t for t in self._ctrl.tasks(self.roottask) if self.check(t)), None)

    def check(self, task, parent = NoArgs) -> bool:
        "wether this controller deals with this task"
        if not (isinstance(task, self.tasktype) and self._check(task)):
            return False
        if parent is NoArgs:
            return True
        return parent is self.roottask

    @staticmethod
    def _check(_) -> bool:
        return True

    @staticmethod
    def _default() -> dict:
        return {}

    @property
    def index(self) -> Optional[Task]:
        "returns the index the new task should have"
        order    = tuple(taskorder(self.configroot.tasks.order.get()))
        ind      = order.index(self.tasktype) + self.side
        previous = order[:ind]

        tasks    = tuple(self._ctrl.tasks(self.roottask))
        for i, tsk in enumerate(tasks[1:]):
            if not isinstance(tsk, previous):
                return i+1
        return len(tasks)

    def observe(self, *args, **kwa):
        "observes the provided task"
        def _check(parent = None, task = None, **_):
            return self.check(task, parent)
        self._ctrl.observe(*args, argstest = _check, **kwa)

class TaskPlotCreator(PlotCreator):
    "Base plotter for tracks"
    _MODEL = TaskPlotModelAccess
    def __init__(self, *args, **kwa):
        super().__init__(*args, **kwa)
        self._ctrl.getGlobal("project").bead.default = None
        if TYPE_CHECKING:
            self._model = TaskPlotModelAccess('', '')

    def observe(self):
        "sets-up model observers"
        super().observe()

        if any(isinstance(i, TaskAccess) for i in self._model.__dict__.values()):
            self._ctrl.observe("updatetask", "addtask", "removetask",
                               lambda **items: self.reset(items))

    def _needsreset(self, items) -> bool:
        if 'parent' in items:
            return self._model.checktask(items['parent'], items['task'])
        else:
            return super()._needsreset(items)

    def _create(self, doc):
        raise NotImplementedError()

    def _reset(self, items, *args):
        raise NotImplementedError()
