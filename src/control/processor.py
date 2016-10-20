#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Processors apply tasks to a data flow"
from abc            import ABCMeta, abstractmethod
from typing         import (Optional, Iterator, Iterable, # pylint: disable=unused-import
                            Tuple, Any)

from model.task     import Task, TrackReaderTask, CycleCreatorTask, TaggingTask
from data           import Track, Cycles
from .lazy          import LazyDict
from .taskcontrol   import TrackData

class Processor(metaclass=ABCMeta):
    u"""
    Main class for processing tasks
    """
    _tasktype = Task # type: type
    def __init__(self, task: Task) -> None:
        self.task = task

    @abstractmethod
    def run(self, args:TrackData.RunArgs):
        u"iterates over possible data"

    @classmethod
    def tasktype(cls):
        u"returns the task type for this processor"
        return cls._tasktype

class CacheMixin:
    u"""
    Cached version of a processor.
    """
    def run(self, args:TrackData.RunArgs):
        u"Iterates through the generator, caching the data"
        # creates an access to a cache which is possibly internal to the generator
        cache = args.data.setCacheDefault(self, dict())
        def _cache(frame):
            frameact  = frame.getaction()
            if frameact is None:
                raise IndexError("Nothing to cache! Set an action prior to mixin")

            dico   = cache.setdefault(frame.parents, LazyDict())
            cached = lambda item: dico.setdefault(item[0], lambda: frameact(item))
            frame.withaction(cached, clear = True)

        args.apply(_cache)

class ActionMixin:
    u"""
    To be used for a task which simply adds an action
    """
    def __init__(self, action):
        self.action = action

    def run(self, args:TrackData.RunArgs):
        u"Iterates through the generator, caching the data"
        action = self.action
        args.apply(lambda frame: frame.withaction(action))

class TrackReaderProcessor(Processor):
    u"Generates output from a CycleCreatorTask"
    _tasktype = TrackReaderTask

    def run(self, args:TrackData.RunArgs):
        u"returns a dask delayed item"
        res        = args.data.setCacheDefault(self, Track(path = self.task.path))
        args.apply((res.beads,), level = self)

class CycleCreatorProcessor(Processor):
    u"Generates output from a CycleCreatorTask"
    _tasktype = CycleCreatorTask

    def run(self, args:TrackData.RunArgs):
        u"iterates through beads and yields cycles"
        task  = self.task
        track = args.first
        args.apply(lambda frame:Cycles(track = track,
                                       data  = frame,
                                       first = task.first,
                                       last  = task.last),
                   level = self)

class SelectionProcessor(Processor):
    u"Generates output from a TaggingTask"
    _tasktype = TaggingTask

    def run(self, args:TrackData.RunArgs):
        u"iterates through beads and yields accepted items"
        elems = tuple(self.task.selection)
        if   self.task.action is self.tasktype().keep:
            args.apply(lambda frame: frame.selecting(elems))

        elif self.task.action is self.tasktype().remove:
            args.apply(lambda frame: frame.discarding(elems))
