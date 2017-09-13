#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Classes defining a type of data treatment.

**Warning** Those definitions must remain data-independant.
"""
from copy           import deepcopy
from pathlib        import Path
from typing         import Sequence, Dict, Set, Tuple, Union, List, Callable, Iterator
from pickle         import dumps as _dumps
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
    disabled = False
    def __init__(self, **kwargs) -> None:
        self.disabled = kwargs.get('disabled', type(self).disabled)
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
        self.__init__(**kwargs)

    def __eq__(self, obj):
        if obj.__class__ is not self.__class__:
            return False

        if hasattr(self, '__getstate__'):
            return obj.__getstate__() == self.__getstate__() # pylint: disable=no-member

        return _dumps(self) == _dumps(obj)

    def __scripting__(self, _):
        """
        Used in  scripting.Tasks for creating a new task

        See peakcalling.FitToHairpinTask for an example.
        """
        return self

    __hash__ = object.__hash__

    @classmethod
    def unique(cls):
        "returns class or parent task if must remain unique"
        return cls

    @classmethod
    def isroot(cls):
        "returns whether the class should be a root"
        return False

    @classmethod
    def isslow(cls) -> bool:
        "whether this task implies long computations"
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

_PATHTYPE = Union[str, Path, Tuple[Union[str,Path],...]]
PATHTYPE  = Union[_PATHTYPE, Dict[str,_PATHTYPE]]
class TrackReaderTask(RootTask):
    "Class indicating that a track file should be added to memory"
    def __init__(self,
                 path:      PATHTYPE = None,
                 beadsonly: bool     = False,
                 copy:      bool     = False, **kwa) -> None:
        super().__init__(**kwa)
        self.path      = path
        self.beadsonly = beadsonly
        self.copy      = copy

class DataSelectionTask(Task):
    "selects some part of the data"
    level                                  = Level.none
    beadsonly: bool                        = None
    samples:   Union[Sequence[int], slice] = None
    phases:    Union[Tuple[int,...], int]  = None
    selected:  List                        = None
    discarded: List                        = None
    cycles:    slice                       = None
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
        self.tags:      Dict[str,Set[int]] = dict(kw.get('tags', []))
        self.selection: Set                = set (kw.get('tags', []))
        self.action:    TagAction          = toenum(TagAction, kw.get('action', 'none'))

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

class CycleCreatorTask(Task):
    "Task for dividing a bead's data into cycles"
    levelin    = Level.bead
    levelou    = Level.cycle
    first: int = None
    last:  int = None
    @classmethod
    def unique(cls):
        "returns class or parent task if must remain unique"
        return cls

class DataFrameTask(Task):
    "Adds it's task to the TrackItem using *withfunction*"
    level                                     = Level.none
    merge                                     = False
    indexes: Sequence[str]                    = ['track', 'bead', 'cycle', 'event']
    measures: Dict[str, Union[Callable, str]] = {}
    @initdefaults(frozenset(locals()))
    def __init__(self, **kwa):
        super().__init__(**kwa)

    def getfunctions(self) -> Iterator[Tuple[str, Callable]]:
        "returns measures, with string changed to methods from np"
        return ((i, self.getfunction(j)) for i, j in self.measures.items())

    @staticmethod
    def indexcolumns(cnt, key = None, frame = None) -> Dict[str, np.ndarray]:
        "adds default columns"
        res = {}
        if frame is not None:
            if frame.track.key:
                res['track'] = np.full(cnt, frame.track.key)
            elif isinstance(frame.track.path, (str, Path)):
                res['track'] = np.full(cnt, str(Path(frame.track.path).name))
            else:
                res['track'] = np.full(cnt, str(Path(frame.track.path[0]).name))

        if key is not None:
            if isinstance(key, tuple) and len(key) == 2:
                res['bead']  = np.full(cnt, key[0])
                res['cycle'] = np.full(cnt, key[1])
            elif np.isscalar(key):
                res['bead'] = np.full(cnt, key)
        return res

    @staticmethod
    def getfunction(name: Union[Callable, str]) -> Callable:
        "returns measures, with string changed to methods from np"
        if isinstance(name, str):
            return getattr(np, f'nan{name}', getattr(np, name, None))
        return name

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

        return lambda dat: dat.withfunction(cpy, beadsonly = self.beadsonly)

TASK_ORDER = ('model.task.RootTask',
              'model.task.DataSelectionTask',
              'cleaning.beadsubtraction.BeadSubtractionTask',
              'cleaning.processor.DataCleaningTask',
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
        yield getattr(__import__(modname, fromlist = (clsname,)), clsname) # type: ignore

__all__ = (tuple(i for i in locals() if i.endswith('Task') and len(i) >= len('Task'))
           + ('TagAction', 'TASK_ORDER'))
