#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Processors apply tasks to a data flow"
from    typing         import TYPE_CHECKING
from    abc            import ABCMeta, abstractmethod
from    functools      import wraps

import  model.task   as     _tasks
from    model.level    import Level
from    data           import Track, Cycles

if TYPE_CHECKING:
    # pylint: disable=unused-import,wrong-import-order,ungrouped-imports
    from typing     import Tuple, Union
    from .runner    import Runner

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
        if isinstance(nspace['tasktype'], type):
            if not issubclass(nspace['tasktype'], _tasks.Task):
                raise TypeError('Only Task classes in the tasktype attribute')
        elif hasattr(nspace['tasktype'], '__iter__'):
            nspace['tasktype'] = tuple(set(nspace['tasktype']))
            if not all(isinstance(tsk, type) and issubclass(tsk, _tasks.Task)
                       for tsk in nspace['tasktype']):
                raise TypeError('"tasktype" should all be Task classes', str(nspace['tasktype']))
        elif name != 'Processor':
            raise AttributeError('"tasktype" must be defined in '+name)
        return super().__new__(mcs, name, bases, nspace)

    def __setattr__(cls, key, value):
        if key in _PROTECTED:
            raise AttributeError('"{}" is read-only'.format(key))
        super().__setattr__(key, value)

class Processor(metaclass=MetaProcessor):
    u"""
    Main class for processing tasks
    """
    tasktype = None # type: Union[type,Tuple[type]]
    def __init__(self, task: _tasks.Task) -> None:
        if not isinstance(task, self.tasktype):
            raise TypeError('"task" must have type '+ str(self.tasktype))
        self.task = task

    @property
    def levelin(self) -> Level:
        u"returns the task's input level"
        if hasattr(self.task, 'level'):
            return self.task.level
        return self.task.levelin

    @property
    def levelou(self) -> Level:
        u"returns the task's output level"
        if hasattr(self.task, 'level'):
            return self.task.level
        return self.task.levelou

    @property
    def levels(self) -> 'Tuple[Level,Level]':
        u"returns the task's level"
        return (self.levelin, self.levelou)

    @abstractmethod
    def run(self, args:'Runner'):
        u"iterates over possible data"

    @staticmethod
    def cache(fcn):
        u"""
        Caches actions.

        The cache is specific to the processor instance.
        It will be cleared if any prior task is updated/added/removed.

        The decorated function can return an action. See TrackItems.withactions
        for an explanation.

        **Note:** default, the data is copied.

        **Note:** The action's closure must *not* contain a task as this can
        have hard-to-debug side-effects.
        """
        @wraps(fcn)
        def _run(self, args:'Runner'):
            cache  = args.data.setCacheDefault(self, dict())
            action = fcn(self, args)

            def _cache(frame):
                if action is not None:
                    frame.withaction(action)
                fcn = frame.getaction()
                if fcn is None:
                    raise IndexError("Nothing to cache! Set an action prior to mixin")

                dico = cache.setdefault(frame.parents, dict())
                cpy  = type(frame).copy
                def _cached(item):
                    ans = dico.get(item[0], None)
                    if ans:
                        return item[0], ans

                    item          = cpy(fcn(item))
                    dico[item[0]] = item[1]
                    return item

                frame.withaction(_cached, clear = True)
                return frame

            args.apply(_cache)
        return _run

    @staticmethod
    def action(fcn):
        u"""
        Adds an action to the currently yielded TrackItems.
        The decorated function is expected to return an action.
        See TrackItems.withactions for an explanation.

        **Note:** The action's closure must *not* contain a task as this can
        have hard-to-debug side-effects.
        """
        @wraps(fcn)
        def _run(self, args:'Runner'):
            act = fcn(self, args)
            args.apply(lambda frame: frame.withaction(act))
        return _run

class TrackReaderProcessor(Processor):
    u"Generates output from a _tasks.CycleCreatorTask"
    tasktype = _tasks.TrackReaderTask

    def run(self, args:'Runner'):
        u"returns a dask delayed item"
        res = args.data.setCacheDefault(self, Track(path = self.task.path))
        args.apply((res.beads,), levels = self.levels)

class CycleCreatorProcessor(Processor):
    u"Generates output from a _tasks.CycleCreatorTask"
    tasktype = _tasks.CycleCreatorTask

    def run(self, args:'Runner'):
        u"iterates through beads and yields cycles"
        kwargs = dict(track = args.first,
                      first = self.task.first,
                      last  = self.task.last)
        args.apply(lambda data: Cycles(data = data, **kwargs),
                   levels = self.levels)

class SelectionProcessor(Processor):
    u"Generates output from a TaggingTask"
    tasktype = _tasks.TaggingTask

    def run(self, args:'Runner'):
        u"iterates through beads and yields accepted items"
        elems = tuple(self.task.selection)
        if   self.task.action is self.tasktype.keep:
            args.apply(lambda frame: frame.selecting(elems))

        elif self.task.action is self.tasktype.remove:
            args.apply(lambda frame: frame.discarding(elems))

class ProtocolProcessor(Processor):
    u"A processor that can deal with any task having the __processor__ attribute"
    tasktype = _tasks.SignalFilterTask.__subclasses__()
    def run(self, args:'Runner'):
        fcn = self.task.__processor__()
        args.apply(iter(fcn(dat) for dat in fcn))
