#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Processors apply tasks to a data flow"
from abc            import ABCMeta, abstractmethod
from typing         import (Optional, Iterator, # pylint: disable=unused-import
                            Tuple, Iterable, Any)
from functools      import wraps

from model.task     import Task, TrackReaderTask, CycleCreatorTask, TaggingTask
from data           import Track, Cycles
from .lazy          import LazyDict
from .taskcontrol   import RunArgs

_PROTECTED = 'tasktype',
class ProtectedDict(dict):
    u"Dictionary with read-only keys"
    def __setitem__(self, key, val):
        if key in _PROTECTED and key in self:
            raise KeyError('"{}" is read-only'.format(key))
        else:
            super().__setitem__(key, val)

    def __delitem__(self, key):
        if key in _PROTECTED:
            raise KeyError('"{}" is read-only'.format(key))
        else:
            super().__delitem__(key)

class MetaProcessor(ABCMeta):
    u"Protects attribute tasktype"
    def __new__(mcs, name, bases, nspace):
        if 'tasktype' not in nspace:
            raise AttributeError('"tasktype" must be defined')
        return super().__new__(mcs, name, bases, nspace)

    @staticmethod
    def __prepare__(*_):
        return ProtectedDict()

    def __setattr__(cls, key, value):
        if key in _PROTECTED:
            raise AttributeError('"{}" is read-only'.format(key))
        super().__setattr__(key, value)

class Processor(metaclass=MetaProcessor):
    u"""
    Main class for processing tasks
    """
    tasktype = Task # type: type
    def __init__(self, task: Task) -> None:
        if not isinstance(task, self.tasktype):
            raise TypeError('"task" must have type "tasktype"')
        self.task = task

    @abstractmethod
    def run(self, args:RunArgs):
        u"iterates over possible data"

    @staticmethod
    def cache(fcn):
        u"Caches actions "
        @wraps(fcn)
        def _run(self, args:RunArgs):
            cache = args.data.setCacheDefault(self, dict())

            def _cache(frame):
                frameact  = frame.getaction()
                if frameact is None:
                    raise IndexError("Nothing to cache! Set an action prior to mixin")

                dico   = cache.setdefault(frame.parents, LazyDict())
                cached = lambda item: dico.setdefault(item[0], lambda: frameact(item))
                frame.withaction(cached, clear = True)

            fcn(self, args)
            args.apply(_cache)
        return _run

    @staticmethod
    def action(fcn):
        u"Adds an action to the currently yielded TrackItems"
        @wraps(fcn)
        def _run(self, args:RunArgs):
            act = fcn(self, args)
            args.apply(lambda frame: frame.withaction(act))
        return _run

class TrackReaderProcessor(Processor):
    u"Generates output from a CycleCreatorTask"
    tasktype = TrackReaderTask

    def run(self, args:RunArgs):
        u"returns a dask delayed item"
        res = args.data.setCacheDefault(self, Track(path = self.task.path))
        args.apply((res.beads,), level = self)

class CycleCreatorProcessor(Processor):
    u"Generates output from a CycleCreatorTask"
    tasktype = CycleCreatorTask

    def run(self, args:RunArgs):
        u"iterates through beads and yields cycles"
        kwargs = dict(track = args.first,
                      first = self.task.first,
                      last  = self.task.last)
        args.apply(lambda data: Cycles(data = data, **kwargs), level = self)

class SelectionProcessor(Processor):
    u"Generates output from a TaggingTask"
    tasktype = TaggingTask

    def run(self, args:RunArgs):
        u"iterates through beads and yields accepted items"
        elems = tuple(self.task.selection)
        if   self.task.action is self.tasktype.keep:
            args.apply(lambda frame: frame.selecting(elems))

        elif self.task.action is self.tasktype.remove:
            args.apply(lambda frame: frame.discarding(elems))
