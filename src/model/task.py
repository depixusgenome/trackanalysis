#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"""
Classes defining a type of data treatment.

**Warning** Those definitions must remain data-independant.
"""
from copy           import deepcopy
from typing         import (Optional, Sequence,  # pylint: disable=unused-import
                            Dict, Callable)
from enum           import Enum, unique
import numpy        as     np

from utils          import toenum, initdefaults
from .level         import Level

class TaskIsUniqueError(Exception):
    u"verifies that the list contains no unique task of type task"
    @classmethod
    def verify(cls, task:'Task', lst):
        u"verifies that the list contains no unique task of type task"
        if task is None:
            return

        tcl = task.unique() if isinstance(task, type) else task

        if tcl is None:
            return

        if any(tcl is other.unique() for other in lst if other.unique()):
            raise cls()

class Task:
    u"Class containing high-level configuration infos for a task"
    def __init__(self, **kwargs) -> None:
        self.disabled = False
        if 'level' in kwargs:
            self.level = toenum(Level, kwargs['level']) # type: Level
        else:
            if 'levelin' in kwargs:
                self.levelin = toenum(Level, kwargs['levelin'])

            if 'levelou' in kwargs:
                self.levelou = toenum(Level, kwargs['levelou'])

        if ('levelin' in kwargs or 'levelou' in kwargs) and ('level' in kwargs):
            raise KeyError('Specify only "level" or both "levelin", "levelou"')

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

    @classmethod
    def unique(cls):
        u"returns class or parent task if must remain unique"
        return cls

    @classmethod
    def isroot(cls):
        u"returns whether the class should be a root"
        return False

    def config(self) -> dict:
        u"returns a deepcopy of its dict which can be safely used in generators"
        return deepcopy(self.__dict__)

class RootTask(Task):
    u"Class indicating that a track file should be created/loaded to memory"
    levelin = Level.project
    levelou = Level.bead

    @classmethod
    def unique(cls):
        u"returns class or parent task if must remain unique"
        return cls

    @classmethod
    def isroot(cls):
        u"returns whether the class should be a root"
        return True

class TrackReaderTask(RootTask):
    u"Class indicating that a track file should be added to memory"
    def __init__(self,
                 path:     Optional[str] = None,
                 beadsonly:bool          = False,
                 copy:     bool          = False) -> None:
        super().__init__()
        self.path      = path # Optional[str]
        self.beadsonly = beadsonly
        self.copy      = copy

@unique
class TagAction(Enum):
    u"type of actions to perform on selected tags"
    none    = 0
    keep    = 1
    remove  = 2

class TaggingTask(Task):
    u"Class for tagging tracks, beads ..."
    none    = TagAction.none
    keep    = TagAction.keep
    remove  = TagAction.remove

    def __init__(self, level:Level, **kw) -> None:
        super().__init__(level = level)
        self.tags      = dict(kw.get('tags', []))  # type: Dict[str,Set[int]]
        self.selection = set (kw.get('tags', []))  # type: Set
        self.action    = toenum(TagAction, kw.get('action', 'none')) # type: TagAction

    def selected(self, item) -> bool:
        u"Returns whether an item is selected"
        if self.action is TagAction.none:
            return False

        return any(item.id in self.tags[tag] for tag in self.selection & set(self.tags))

    def process(self, item) -> bool:
        u"Returns whether an item is kept"
        if self.action is TagAction.none:
            return True

        return self.selected(item) == (self.action == TagAction.keep)

    def clean(self):
        u"Removes tags not in the parent"
        self.selection &= set(self.tags)

class CycleCreatorTask(Task):
    u"Task for dividing a bead's data into cycles"
    levelin = Level.bead
    levelou = Level.cycle

    @classmethod
    def unique(cls):
        u"returns class or parent task if must remain unique"
        return cls

class DataFunctorTask(Task):
    u"Adds it's task to the TrackItem using *withfunction*"
    copy     = False
    beadonly = True
    @initdefaults
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
            return lambda dat: dat.withfunction(fcn, beadonly = self.beadonly)
        else:
            return lambda dat: dat.withfunction(cpy, beadonly = self.beadonly)
