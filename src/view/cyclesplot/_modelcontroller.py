#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"access to the model"

from    typing                      import Optional, Sequence, Tuple, cast
from    copy                        import deepcopy

from    utils                       import NoArgs, updatedeepcopy
from    model.task                  import Task
from    eventdetection.processor    import ExtremumAlignmentTask as AlignmentTask
from    cordrift.processor          import DriftTask
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

class SpecificTaskController(TrackPlotModelController):
    "access to tasks"
    tasktype   = None # type: type
    def __init__(self, *args):
        super().__init__(*args)
        cnf = self.getRootConfig().tasks
        cnf[self.configname].default = self.tasktype() # pylint: disable=not-callable

    @property
    def configname(self) -> str:
        "returns the config name"
        return self.__class__.__name__.lower()[:-len('Controller')]

    @property
    def configtask(self) -> Task:
        "returns the config task"
        return self.getRootConfig().tasks[self.configname].get()

    @configtask.setter
    def configtask(self, task) -> Task:
        "returns the config task"
        task = deepcopy(task)
        self.getRootConfig().tasks[self.configname] = task
        return task

    def remove(self):
        "removes the task"
        task = self.task
        if task is not None:
            self._ctrl.removeTask(self.roottask, task)

    def update(self, **kwa):
        "removes the task"
        root = self.roottask
        task = self.task
        if task is None:
            item  = updatedeepcopy(self.configtask, **kwa)
            self._ctrl.addTask(root, item, index = self.index)
        else:
            self._ctrl.updateTask(root, task, **kwa)

    @property
    def task(self) -> Optional[Task]:
        "returns the task if it exists"
        return next((t for t in self._ctrl.tasks(self.roottask) if self.check(t)), None)

    def check(self, task, parent = NoArgs) -> bool:
        "wether this controller deals with this task"
        if not (isinstance(task, self.tasktype) and self._check(task)):
            return False
        if parent is NoArgs:
            return True
        return parent is self.roottask

    def _check(self, task) -> bool:
        raise NotImplementedError()

    @property
    def index(self) -> Optional[Task]:
        "returns the index the new task should have"
        raise NotImplementedError()

    def observe(self, *args, **kwa):
        "observes the provided task"
        def _check(parent = None, task = None, **_):
            return self.check(task, parent)
        self._ctrl.observe(*args, argstest = _check, **kwa)

class AlignmentController(SpecificTaskController):
    "access to aligment"
    tasktype = AlignmentTask
    def _check(self, task) -> bool:
        return True

    @property
    def index(self) -> Optional[Task]:
        "returns the index the new task should have"
        return 1

class DriftPerBeadController(SpecificTaskController):
    "access to drift per bead"
    tasktype = DriftTask
    def _check(self, task) -> bool:
        return task.onbeads

    @property
    def index(self) -> Optional[Task]:
        "returns the index the new task should have"
        tasks = tuple(self._ctrl.tasks(self.roottask))
        return 2 if len(tasks) > 1 and isinstance(tasks[1], AlignmentTask) else 1

class DriftPerCycleController(SpecificTaskController):
    "access to drift per cycle"
    tasktype = DriftTask
    def _check(self, task) -> bool:
        return not task.onbeads

    @property
    def index(self) -> Optional[Task]:
        "returns the index the new task should have"
        tasks = tuple(self._ctrl.tasks(self.roottask))
        if   len(tasks) > 3 and isinstance(tasks[2], DriftTask):
            return 3
        elif len(tasks) > 2 and isinstance(tasks[1], (AlignmentTask, DriftTask)):
            return 2
        else:
            return 1

class CyclesModelController(TrackPlotModelController):
    "Model for Cycles View"
    _CACHED = 'base.stretch', 'base.bias', 'sequence.key', 'sequence.peaks'
    def __init__(self, key:str, ctrl:Controller) -> None:
        super().__init__(key, ctrl)
        self.driftperbead  = DriftPerBeadController(key, ctrl)
        self.driftpercycle = DriftPerCycleController(key, ctrl)
        self.alignment     = AlignmentController(key, ctrl)

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
