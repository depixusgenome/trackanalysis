#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"access to the model"

from    typing                      import Optional, Sequence, Tuple, cast
from    utils                       import NoArgs, updatecopy, updatedeepcopy
from    model.task                  import Task
from    cordrift.processor          import DriftTask
from    eventdetection.processor    import (ExtremumAlignmentTask as AlignmentTask,
                                            EventDetectionTask)
from    control                     import Controller
from    ..plotutils                 import TrackPlotModelController, readsequence

def _rootconfigprop(attr):
    "returns a property which links to the config"
    # pylint: disable=protected-access
    def _getter(self):
        return self.getRootConfig()[attr].get()

    def _setter(self, val):
        return self.getRootConfig()[attr].set(val)

    hmsg  = "link to config's {}".format(attr)
    return property(_getter, _setter, None, hmsg)

def _configprop(attr):
    "returns a property which links to the config"
    def _getter(self):
        return self.getConfig()[attr].get()

    def _setter(self, val):
        self.getConfig()[attr].set(val)

    hmsg  = "link to config's {}".format(attr)
    return property(_getter, _setter, None, hmsg)

def _beadorconfig(attr):
    "returns a property which links to the current bead or the config"
    def _getter(self):
        value = self.getCurrent()[attr].get().get(self.bead, NoArgs)
        if value is not NoArgs:
            return value
        return self.getConfig()[attr].get()

    def _setter(self, val):
        cache = self.getCurrent()[attr].get()
        if val == self.getConfig()[attr].get():
            cache.pop(self.bead, None)
        else:
            cache[self.bead] = val
    hmsg  = "link to config's {}".format(attr)
    return property(_getter, _setter, None, hmsg)

ORDER = tuple, AlignmentTask, DriftTask, EventDetectionTask
class SpecificTaskController(TrackPlotModelController):
    "access to tasks"
    TASKTYPE = None   # type: type
    SIDE     = 'LEFT'
    def __init__(self, *args):
        super().__init__(*args)
        cnf = self.getRootConfig().tasks
        cnf[self.configname].default = self.TASKTYPE() # pylint: disable=not-callable

    @property
    def configname(self) -> str:
        "returns the config name"
        return self.__class__.__name__.lower()[:-len('Controller')]

    @property
    def configtask(self) -> Task:
        "returns the config task"
        return self.getRootConfig().tasks[self.configname]

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

    def check(self, task, parent = NoArgs) -> bool:
        "wether this controller deals with this task"
        if not (isinstance(task, self.TASKTYPE) and self._check(task)):
            return False
        if parent is NoArgs:
            return True
        return parent is self.roottask

    @staticmethod
    def _check(_) -> bool:
        return True

    @property
    def index(self) -> Optional[Task]:
        "returns the index the new task should have"
        tasks = tuple(self._ctrl.tasks(self.roottask))
        ind   = ORDER.index(self.TASKTYPE) + (1 if self.SIDE == 'RIGHT' else 0)
        rem   = ORDER[:ind] # type: ignore
        for i, tsk in enumerate(tasks[1:]):
            if not isinstance(tsk, rem):
                return i+1
        return len(tasks)

    def observe(self, *args, **kwa):
        "observes the provided task"
        def _check(parent = None, task = None, **_):
            return self.check(task, parent)
        self._ctrl.observe(*args, argstest = _check, **kwa)

class AlignmentController(SpecificTaskController):
    "access to aligment"
    TASKTYPE = AlignmentTask

class DriftPerBeadController(SpecificTaskController):
    "access to drift per bead"
    TASKTYPE = DriftTask
    @staticmethod
    def _check(task) -> bool:
        return task.onbeads

class DriftPerCycleController(SpecificTaskController):
    "access to drift per cycle"
    TASKTYPE = DriftTask
    SIDE     = 'RIGHT'
    @staticmethod
    def _check(task) -> bool:
        return not task.onbeads

class EventDetectionController(SpecificTaskController):
    "access to drift per cycle"
    TASKTYPE = EventDetectionTask

class CyclesModelController(TrackPlotModelController):
    "Model for Cycles View"
    _CACHED = 'base.stretch', 'base.bias', 'sequence.key', 'sequence.peaks'
    def __init__(self, key:str, ctrl:Controller) -> None:
        super().__init__(key, ctrl)
        self.driftperbead   = DriftPerBeadController(key, ctrl)
        self.driftpercycle  = DriftPerCycleController(key, ctrl)
        self.alignment      = AlignmentController(key, ctrl)
        self.eventdetection = EventDetectionController(key, ctrl)

        self.getConfig().defaults = {'binwidth'          : .003,
                                     'minframes'         : 10,
                                     'base.bias'         : None,
                                     'base.bias.step'    : .0001,
                                     'base.bias.ratio'   : .25,
                                     'base.stretch'      : 8.8e-4,
                                     'base.stretch.start': 5.e-4,
                                     'base.stretch.step' : 1.e-5,
                                     'base.stretch.end'  : 1.5e-3,
                                     'sequence.path' : None,
                                     'sequence.key'  : None,
                                    }
        self.getConfig().sequence.peaks.default = None
        for attr in self._CACHED:
            self.getCurrent()[attr].setdefault(None)
        self.clearcache()

    def clearcache(self):
        u"updates the model when a new track is loaded"
        self.getCurrent().update({i: dict() for i in self._CACHED})

    sequencepath = cast(Optional[str],           _rootconfigprop('last.path.fasta'))
    oligos       = cast(Optional[Sequence[str]], _rootconfigprop('oligos'))
    binwidth     = cast(float,                   _configprop  ('binwidth'))
    minframes    = cast(int,                     _configprop  ('minframes'))
    stretch      = cast(float,                   _beadorconfig('base.stretch'))
    bias         = cast(Optional[float],         _beadorconfig('base.bias'))
    peaks        = cast(Optional[Tuple[float,float,float,float]],
                        _beadorconfig('sequence.peaks'))

    _sequencekey = cast(Optional[str],           _beadorconfig('sequence.key'))
    @property
    def sequencekey(self) -> Optional[str]:
        "returns the current sequence key"
        key  = self._sequencekey
        dseq = readsequence(self.sequencepath)
        return next(iter(dseq), None) if key not in dseq else key

    @sequencekey.setter
    def sequencekey(self, value) -> Optional[str]:
        self._sequencekey = value
        return self._sequencekey

    def checktask(self, root, task):
        "checks wether a task belongs to the model"
        if not any(val.check(task) for val in self.__dict__.values()
                   if isinstance(val, SpecificTaskController)):
            return False

        return root is self.roottask

    def runbead(self):
        "returns a tuple (dataitem, bead) to be displayed"
        track = self.track
        if track is None:
            return None, None, None

        root  = self.roottask
        for task in tuple(self._ctrl.tasks(root))[3::-1]:
            if self.checktask(root, task):
                ibead = self.bead
                beads = next(iter(self._ctrl.run(root, task, copy = True)))
                return track, beads[ibead,...], ibead

        return track, track.cycles[self.bead,...], self.bead

    def observetasks(self, *args, **kwa):
        "observes the provided task"
        def _check(parent = None, task = None, **_):
            return self.checktask(parent, task)
        self._ctrl.observe(*args, argstest = _check, **kwa)
