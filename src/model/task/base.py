#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Classes defining a type of data treatment.

**Warning** Those definitions must remain data-independant.
"""
from   typing       import Dict, Any
from   copy         import deepcopy
from   pickle       import dumps as _dumps

import numpy        as     np

from   utils        import toenum, initdefaults
from   ..level      import Level

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

        names = ['levelin', 'levelou'] if not hasattr(self, 'level') else ['level']
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

    def config(self) -> Dict[str,Any]:
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

class DataFunctorTask(Task):
    "Adds it's task to the TrackItem using *withfunction*"
    copy      = False
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
            return lambda dat: dat.withfunction(fcn)

        return lambda dat: dat.withfunction(cpy)
