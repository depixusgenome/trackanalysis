#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Monkeypatches tasks and provides a simpler access to usual tasks
"""
from copy                   import deepcopy
from enum                   import Enum
from utils                  import update

import anastore
from cordrift.processor         import DriftTask
from eventdetection.processor   import ExtremumAlignmentTask, EventDetectionTask
from peakfinding.processor      import PeakSelectorTask
from peakcalling.processor      import FitToHairpinTask
from model.task                 import * # pylint: disable=wildcard-import,unused-wildcard-import
from model.task                 import __all__ as __all_tasks__, Task

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
    selection      = 'selection'
    alignment      = 'alignment'
    driftperbead   = 'driftperbead'
    driftpercycle  = 'driftpercycle'
    cycles         = 'cycles'
    eventdetection = 'eventdetection'
    peakselector   = 'peakselector'
    fittohairpin   = 'fittohairpin'

    @staticmethod
    def defaults():
        "returns default tasks"
        return dict(selection      = DataSelectionTask(),
                    alignment      = ExtremumAlignmentTask(),
                    driftperbead   = DriftTask(onbeads = True),
                    driftpercycle  = DriftTask(onbeads = False),
                    cycles         = CycleCreatorTask(),
                    eventdetection = EventDetectionTask(),
                    peakselector   = PeakSelectorTask(),
                    fittohairpin   = FitToHairpinTask())

    def default(self):
        "returns default tasks"
        return self.defaults()[self.value]

    @classmethod
    def create(cls, arg, **kwa):
        "returns the task associated to the argument"
        if isinstance(arg, (str, cls)):
            return cls(arg)(**kwa)

        elif isinstance(arg, tuple):
            return cls(arg[0])(**arg[1], **kwa)

        else:
            assert isinstance(arg, Task)
            if len(kwa):
                return update(deepcopy(arg), **kwa)
            return arg

    def __call__(self, *resets, current = None, **kwa):
        cnf = self.default() if current is None else deepcopy(current)
        cls = type(cnf)
        if Ellipsis in resets:
            resets = tuple(i for i in resets if i is not Ellipsis)

        kwa.update({i: getattr(cls, i) for i, j in kwa.items() if j is RESET})
        kwa.update({i: getattr(cls, i) for i in resets})
        task = update(deepcopy(cnf), **kwa)
        self.save(task)
        return task

    class _TaskGetter:
        def __get__(self, obj, tpe):
            return tpe.create if obj is None else obj

    get = _TaskGetter()

def dumps(self, **kwa):
    "returns the json configuration"
    kwa.setdefault('saveall', False)
    kwa.setdefault('indent', 4)
    kwa.setdefault('ensure_ascii', False)
    kwa.setdefault('sort_keys', True)
    kwa.setdefault('patch', None)
    return anastore.dumps(self, **kwa)
Task.dumps = dumps

__all__ = __all_tasks__ + ('Tasks', 'DriftTask', 'ExtremumAlignmentTask',
                           'EventDetectionTask', 'PeakSelectorTask',
                           'FitToHairpinTask')
