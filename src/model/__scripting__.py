#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Monkeypatches tasks and provides a simpler access to usual tasks
"""
import sys
from pathlib                import Path

from copy                   import deepcopy
from enum                   import Enum
from utils                  import update

import anastore
from control.taskcontrol        import create as _create
from cleaning.processor         import DataCleaningTask
from cordrift.processor         import DriftTask
from eventdetection.processor   import ExtremumAlignmentTask, EventDetectionTask
from peakfinding.processor      import PeakSelectorTask
from peakcalling.processor      import FitToHairpinTask, BeadsByHairpinTask
from .task                      import * # pylint: disable=wildcard-import,unused-wildcard-import
from .task                      import Task, TrackReaderTask
from .task.dataframe            import DataFrameTask

assert 'scripting' in sys.modules
RESET = type('Reset', (), {})
class Tasks(Enum):
    """
    Possible tasks

    These can be created as follows:

        >>> task = Tasks.alignment()
        >>> assert isinstance(task, ExtremumAlignmentTask)

    Attribute values can be set
        >>> assert Tasks.peakselector().align is not None         # default value
        >>> assert Tasks.peakselector(align = None).align is None # change default
        >>> assert Tasks.peakselector('align').align is not None  # back to true default
        >>> assert Tasks.peakselector(align = None).align is None # change default
    """
    cleaning       = 'cleaning'
    selection      = 'selection'
    alignment      = 'alignment'
    driftperbead   = 'driftperbead'
    driftpercycle  = 'driftpercycle'
    cycles         = 'cycles'
    eventdetection = 'eventdetection'
    peakselector   = 'peakselector'
    fittohairpin   = 'fittohairpin'
    beadsbyhairpin = 'beadsbyhairpin'
    dataframe      = 'dataframe'

    @staticmethod
    def defaults():
        "returns default tasks"
        return dict(cleaning       = DataCleaningTask(),
                    selection      = DataSelectionTask(),
                    alignment      = ExtremumAlignmentTask(),
                    driftperbead   = DriftTask(onbeads = True),
                    driftpercycle  = DriftTask(onbeads = False),
                    cycles         = CycleCreatorTask(),
                    eventdetection = EventDetectionTask(),
                    peakselector   = PeakSelectorTask(),
                    fittohairpin   = FitToHairpinTask(),
                    beadsbyhairpin = BeadsByHairpinTask(),
                    dataframe      = DataFrameTask())

    def default(self):
        "returns default tasks"
        return self.defaults()[self.value]

    @classmethod
    def create(cls, *args, beadsonly = True, **kwa):
        "returns the task associated to the argument"
        if len(args) == 1:
            return cls.__create(args[0], kwa, beadsonly)
        return [cls.__create(i, kwa, beadsonly) for i in args]

    @classmethod
    def tasklist(cls, *tasks, **kwa):
        "Same as create except that a list may be completed as necessary"
        lst   = cls.get(*tasks, **kwa)
        if isinstance(lst, Task):
            lst = [lst]

        order = FitToHairpinTask, PeakSelectorTask, EventDetectionTask,
        for i, itm in enumerate(order[:-1]):
            ind = next((i for i, j in enumerate(lst) if isinstance(j, itm)), None)
            if ind is None:
                continue

            if ind == 0 or not isinstance(lst[ind-1], order[i+1]):
                name = order[ind+1].__name__.lower().replace('Task', '')
                lst.insert(ind, cls.get(name, **kwa))
        return lst

    @classmethod
    def processors(cls, *args, copy = True, beadsonly = True):
        "returns an iterator over the result of provided tasks"
        procs      = _create(cls.tasklist(*args, beadsonly = beadsonly))
        procs.copy = copy
        return procs

    @classmethod
    def apply(cls, *args, copy = True, beadsonly = True):
        "returns an iterator over the result of provided tasks"
        return next(iter(cls.processors(*args, beadsonly = beadsonly).run(copy = copy)))

    def __call__(self, *resets, **kwa):
        current = kwa.pop('current', None)
        cnf     = self.default() if current is None else deepcopy(current)
        cls     = type(cnf)
        if Ellipsis in resets:
            resets = tuple(i for i in resets if i is not Ellipsis)

        kwa.update({i: getattr(cls, i) for i, j in kwa.items() if j is RESET})
        kwa.update({i: getattr(cls, i) for i in resets})
        task = update(deepcopy(cnf), **kwa)
        task = getattr(task, '__scripting__', lambda x: task)(kwa)
        self.save(task)
        return task

    class _TaskGetter:
        def __get__(self, obj, tpe):
            return tpe.create if obj is None else obj

    get = _TaskGetter()

    @classmethod
    def __create(cls, arg, kwa, beadsonly):
        if isinstance(arg, cls):
            return arg(**kwa)

        if isinstance(arg, Task):
            return update(deepcopy(arg), **kwa)

        if isinstance(arg, str) and arg in cls.__members__:
            return cls(arg)(**kwa)

        if (isinstance(arg, (Path, str))
                or (isinstance(arg, (tuple, list))
                    and isinstance(i, (Path, str)) for i in arg)):
            info = dict(kwa)
            info.setdefault('path', arg)
            info.setdefault('beadsonly', beadsonly)
            return TrackReaderTask(**info)

        if isinstance(arg, (tuple, list)) and len(arg) == 2:
            return cls(arg[0])(**arg[1], **kwa)

        raise RuntimeError('arguments are unexpected')

def dumps(self, **kwa):
    "returns the json configuration"
    kwa.setdefault('saveall', False)
    kwa.setdefault('indent', 4)
    kwa.setdefault('ensure_ascii', False)
    kwa.setdefault('sort_keys', True)
    kwa.setdefault('patch', None)
    return anastore.dumps(self, **kwa)
Task.dumps = dumps # type: ignore

__all__ = ('Task', 'RootTask', 'Level', 'TASK_ORDER', 'taskorder',
           'TrackReaderTask', 'CycleCreatorTask', 'DataSelectionTask',
           'Tasks', 'DriftTask', 'ExtremumAlignmentTask',
           'EventDetectionTask', 'PeakSelectorTask',
           'FitToHairpinTask', 'DataFrameTask')
