#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"""
Classes defining a type of data treatment.

**Warning** Those definitions must remain data-independant.
"""
from typing         import (Optional, Sequence,  # pylint: disable=unused-import
                            Dict, Any)
from enum           import Enum, unique

import numpy

from utils          import toenum
from .level         import Level
from signalfilter   import (ForwardBackwardFilter, # pylint: disable=no-name-in-module
                            NonLinearFilter)

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

    @classmethod
    def unique(cls):
        u"returns class or parent task if must remain unique"
        return cls

class TrackReaderTask(Task):
    u"Class indicating that a track file should be added to memory"
    levelin = Level.project
    levelou = Level.bead
    def __init__(self, path: Optional[str] = None) -> None:
        super().__init__()
        self.path = path # Optional[str]

    @classmethod
    def unique(cls):
        u"returns class or parent task if must remain unique"
        return cls

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

class SignalFilterTask(Task):
    u"Filters time series"
    level = Level.none
    _COPY = True
    def __init__(self, **kwa):
        super().__init__(self, **kwa)
        for name in set(self.__dict__).intersection(set(kwa)):
            setattr(self, name, kwa.get(name))
        self.copy = kwa.get('copy', self._COPY) # type: bool

    def __processor__(self):
        cpy =  self.__class__.__bases__[1]()
        for name, val in self.__dict__.items():
            if hasattr(cpy, name):
                setattr(cpy, name, val)

        if self.copy:
            fcn = lambda val: cpy(numpy.copy(val))
        else:
            fcn = cpy
        return lambda dat: dat.withfunction(fcn, beadonly = True)

class ForwardBackwardFilterTask(SignalFilterTask, ForwardBackwardFilter):
    u"Filters time series using the forward-backward algorithm"

class NonLinearFilterTask(SignalFilterTask, NonLinearFilter):
    u"Filters time series using the forward-backward algorithm"
