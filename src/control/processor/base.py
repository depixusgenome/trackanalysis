#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Processors apply tasks to a data flow"
from    abc         import ABCMeta, abstractmethod
from    functools   import wraps
from    typing      import TYPE_CHECKING, Callable, Tuple

import  model.task   as     _tasks
from    model.level import Level
from    data        import Track

if TYPE_CHECKING:
    # pylint: disable=unused-import,wrong-import-order,ungrouped-imports
    from typing     import Union
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

class TaskTypeDescriptor:
    u"""
    Dynamically finds all Task subclasses implementing
    the __processor__ protocol.
    """
    def __get__(self, obj, tpe):
        return getattr(tpe, '_tasktypes')()

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
        elif name != 'Processor' and not isinstance(nspace['tasktype'], TaskTypeDescriptor):
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
    def levels(self) -> Tuple[Level,Level]:
        u"returns the task's level"
        return (self.levelin, self.levelou)

    @abstractmethod
    def run(self, args:'Runner'):
        u"iterates over possible data"

    def config(self) -> dict:
        u"Returns a copy of a task's dict"
        return self.task.config()

    def caller(self) -> Callable:
        u"Returns an instance of the task's first callable parent class"
        tpe   = type(self.task)
        bases = list(tpe.__bases__)
        while len(bases):
            cls = bases.pop(0)

            if (hasattr(cls, '__call__')
                    and cls.__name__[0] != '_'
                    and not issubclass(cls, _tasks.Task)):
                return cls(**self.task.config())

            bases.extend(cls.__bases__)

        raise TypeError("Could not find a functor base type in "+str(tpe))

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
                act = frame.getaction()
                if act is None:
                    raise IndexError("Nothing to cache! Set an action prior to mixin")

                dico = cache.setdefault(frame.parents, dict())
                cpy  = type(frame).copy
                def _cached(item):
                    ans = dico.get(item[0], None)
                    if ans:
                        return item[0], ans

                    item          = cpy(act(item))
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
        if self.task.levelou is Level.cycle:
            args.apply((res.cyclesonly if self.task.beadsonly else res.cycles,),
                       levels = self.levels)
        else:
            args.apply((res.beadsonly if self.task.beadsonly else res.beads,),
                       levels = self.levels)

class CycleCreatorProcessor(Processor):
    u"Generates output from a _tasks.CycleCreatorTask"
    tasktype = _tasks.CycleCreatorTask

    def run(self, args:'Runner'):
        u"iterates through beads and yields cycles"
        kwargs = self.task.first, self.task.last
        args.apply(lambda data: data[...,...].withphases(*kwargs), levels = self.levels)

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

    tasktype = TaskTypeDescriptor()

    @staticmethod
    def _tasktypes():
        treating = _tasks.Task.__subclasses__()
        def _run():
            while len(treating):
                cur = treating.pop()
                if hasattr(cur, '__processor__'):
                    yield cur
                treating.extend(cur.__subclasses__())
        return tuple(_run())

    def run(self, args:'Runner'):
        args.apply(self.task.__processor__())
