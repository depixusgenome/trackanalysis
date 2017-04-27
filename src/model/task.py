#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Classes defining a type of data treatment.

**Warning** Those definitions must remain data-independant.
"""
from copy           import deepcopy
from typing         import (Optional, Sequence,  # pylint: disable=unused-import
                            Dict, Callable, Set, Tuple, Union, List)
from enum           import Enum, unique
import numpy        as     np

from utils          import toenum, initdefaults
from .level         import Level

class TaskIsUniqueError(Exception):
    "verifies that the list contains no unique task of type task"
    @classmethod
    def verify(cls, task:'Task', lst):
        "verifies that the list contains no unique task of type task"
        if task is None:
            return

        tcl = task.unique() if isinstance(task, type) else task

        if tcl is None:
            return

        if any(tcl is other.unique() for other in lst if other.unique()):
            raise cls()

class Task:
    "Class containing high-level configuration infos for a task"
    def __init__(self, **kwargs) -> None:
        self.disabled = kwargs.get('disabled', False)
        if 'level' in kwargs:
            self.level = toenum(Level, kwargs['level']) # type: Level
        else:
            if 'levelin' in kwargs:
                self.levelin = toenum(Level, kwargs['levelin'])

            if 'levelou' in kwargs:
                self.levelou = toenum(Level, kwargs['levelou'])

        if ('levelin' in kwargs or 'levelou' in kwargs) and ('level' in kwargs):
            raise KeyError('Specify only "level" or both "levelin", "levelo"')

        names = ('level',) # type: Sequence[str]
        if not hasattr(self, 'level'):
            names = ('levelin', 'levelou')

        for name in names:
            if not hasattr(self, name):
                raise AttributeError('"{}" in {} is not specified'
                                     .format(name, self.__class__))
            if not isinstance(getattr(self, name), Level):
                raise TypeError('"{}" must be of type Level'.format(name))

    def __setstate__(self, kwargs):
        self.__dict__.update(self.__class__(**kwargs).__dict__)

    def __eq__(self, obj):
        if obj.__class__ is not self.__class__:
            return False
        if hasattr(self, '__getstate__'):
            return obj.__getstate__() == self.__getstate__() # pylint: disable=no-member
        else:
            return obj.__dict__ == self.__dict__

    __hash__ = object.__hash__

    @classmethod
    def unique(cls):
        "returns class or parent task if must remain unique"
        return cls

    @classmethod
    def isroot(cls):
        "returns whether the class should be a root"
        return False

    def config(self) -> dict:
        "returns a deepcopy of its dict which can be safely used in generators"
        return deepcopy(self.__dict__)

class RootTask(Task):
    "Class indicating that a track file should be created/loaded to memory"
    levelin = Level.project
    levelou = Level.bead

    @classmethod
    def unique(cls):
        "returns class or parent task if must remain unique"
        return cls

    @classmethod
    def isroot(cls):
        "returns whether the class should be a root"
        return True

class TrackReaderTask(RootTask):
    "Class indicating that a track file should be added to memory"
    def __init__(self,
                 path:     Union[str, Tuple[str,...], None] = None,
                 beadsonly:bool          = False,
                 copy:     bool          = False) -> None:
        super().__init__()
        self.path      = path
        self.beadsonly = beadsonly
        self.copy      = copy

class DataSelectionTask(Task):
    "selects some part of the data"
    level     = Level.none
    beadsonly = None    # type: Optional[bool]
    samples   = None    # type: Union[Sequence[int], slice, None]
    phases    = None    # type: Union[Tuple[int,...], int, None]
    selected  = None    # type: Optional[List]
    discarded = None    # type: Optional[List]
    cycles    = None    # type: Optional[slice]
    @initdefaults(frozenset(locals()) - {'level'})
    def __init__(self, **_) -> None:
        super().__init__()

@unique
class TagAction(Enum):
    "type of actions to perform on selected tags"
    none    = 0
    keep    = 1
    remove  = 2

class TaggingTask(Task):
    "Class for tagging tracks, beads ..."
    none    = TagAction.none
    keep    = TagAction.keep
    remove  = TagAction.remove

    def __init__(self, level:Level, **kw) -> None:
        super().__init__(level = level)
        self.tags      = dict(kw.get('tags', []))  # type: Dict[str,Set[int]]
        self.selection = set (kw.get('tags', []))  # type: Set
        self.action    = toenum(TagAction, kw.get('action', 'none')) # type: TagAction

    def selected(self, item) -> bool:
        "Returns whether an item is selected"
        if self.action is TagAction.none:
            return False

        return any(item.id in self.tags[tag] for tag in self.selection & set(self.tags))

    def process(self, item) -> bool:
        "Returns whether an item is kept"
        if self.action is TagAction.none:
            return True

        return self.selected(item) == (self.action == TagAction.keep)

    def clean(self):
        "Removes tags not in the parent"
        self.selection &= set(self.tags)

class DiscardedBeadsTask(Task):
    "Class for removing beads ..."
    level = Level.bead
    beads = [] # type: List[int]
    @initdefaults('beads')
    def __init__(self, **_) -> None:
        super().__init__()

class CycleCreatorTask(Task):
    "Task for dividing a bead's data into cycles"
    levelin = Level.bead
    levelou = Level.cycle

    @classmethod
    def unique(cls):
        "returns class or parent task if must remain unique"
        return cls

class DataFunctorTask(Task):
    "Adds it's task to the TrackItem using *withfunction*"
    copy      = False
    beadsonly = True
    @initdefaults(frozenset(locals()))
    def __init__(self, **kwa):
        super().__init__(**kwa)

    def __processor__(self):
        for cls in self.__class__.__bases__:
            if hasattr(cls, '__call__') and not issubclass(cls, Task):
                cpy = cls(**self.config())
                break
        else:
            raise TypeError("Could not find a functor base type in "+str(self.__class__))

        if self.copy:
            fcn = lambda val: cpy(np.copy(val)) # pylint: disable=not-callable
            return lambda dat: dat.withfunction(fcn, beadsonly = self.beadsonly)
        else:
            return lambda dat: dat.withfunction(cpy, beadsonly = self.beadsonly)

TASK_ORDER = ('model.task.RootTask',
              'model.task.DataSelectionTask',
              'eventdetection.processor.ExtremumAlignmentTask',
              'cordrift.processor.DriftTask',
              'eventdetection.processor.EventDetectionTask',
              'peakfinding.processor.PeakSelectorTask',
              'peakcalling.processor.FitToHairpinTask',
             )
def taskorder(lst):
    "yields a list of task types in the right order"
    for itm in lst:
        modname, clsname = itm[:itm.rfind('.')], itm[itm.rfind('.')+1:]
        yield getattr(__import__(modname, fromlist = (clsname,)), clsname)

__all__  = tuple(i for i in locals() if i.endswith('Task') and len(i) >= len('Task'))
__all__ += 'TagAction', 'TASK_ORDER' # type: ignore
