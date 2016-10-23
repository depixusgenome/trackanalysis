#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"""
Classes defining a type of data treatment.

**Warning** Those definitions must remain data-independant.
"""
from typing     import Optional, Sequence # pylint: disable=unused-import
from enum       import Enum, unique
from .level     import Level

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
            self.level = kwargs['level'] # type: Level
        else:
            if 'levelin' in kwargs:
                self.levelin = kwargs['levelin']

            if 'levelou' in kwargs:
                self.levelou = kwargs['levelou']

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
    locals().update(TagAction.__members__)                # type: ignore
    def __init__(self, level:Level, **kw) -> None:
        super().__init__(level = level)
        self.tags      = dict(kw.get('tags', []))         # type: Dict[str,Set[int]]
        self.selection = set (kw.get('tags', []))         # type: Set
        self.action    = kw.get('action', TagAction.none) # type: TagAction

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

class FlatEventsExtractionTask(Task):
    u"Task for extracting flat events from a cycle"
    levelin = Level.cycle
    levelou = Level.event

    @classmethod
    def unique(cls):
        u"returns class or parent task if must remain unique"
        return cls

class DriftComputationTask(Task):
    u"All tasks related to drift removal"

class DCTFlatEventsCollapseTask(DriftComputationTask):
    u"Task that uses flat events to estimate the correlated drift"

class DCTMedianDynamicsTask(DriftComputationTask):
    u"""
    Task that estimates drifts using the integral of the median derivate
    between all cycles or beads"
    """

class FormulaTask(Task):
    u"Task that transforms data using whatever function"
    def __init__(self, **kw) -> None:
        super().__init__(**kw)
        self.formula = str(kw.get('formula', ''))
