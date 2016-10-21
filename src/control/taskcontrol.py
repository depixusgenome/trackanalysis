#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Base controler"
from types          import LambdaType, FunctionType, MethodType
from typing         import Union
from typing         import (Iterator, List,     # pylint: disable=unused-import
                            Tuple, Any, Optional)
from itertools      import groupby

from model.task     import Task, TrackReaderTask
from model.task     import TaskIsUniqueError
from data           import TrackItems
from .event         import Controler, NoEmission

def isfunction(fcn) -> bool:
    u"Returns whether the object is a function"
    return isinstance(fcn, (LambdaType, FunctionType, MethodType))

def _version():
    i = 0
    while True:
        i = i+1
        yield i

class CacheItem:
    u"Holds cache and its version"
    __slots__ = ('_proc', '_cache')
    _VERSION  = _version()
    def __init__(self, proc):
        self._proc    = proc         # type: Processor
        self._cache   = (0, None)    # type: Tuple[int,Any]

    def isitem(self, tsk) -> bool:
        u"returns the index of the provided task"
        return tsk is self.proc or tsk is self.proc.task

    def _getCache(self, old):
        u"Delayed access to the cache"
        def _call():
            version, cache = self._cache
            if old != version:
                return None
            return cache
        return _call

    def setCacheDefault(self, item):
        "Sets the cache if it does not exist yet"
        version, cache = self._cache
        if cache is None:
            cache = item() if isfunction(item) else item
            nvers = next(self._VERSION)
            if version == self._cache[0]:
                self.setCache(cache, nvers)
        return cache

    def setCache(self, cache, version = None):
        u"Sets the cache and its version"
        if version is None:
            version = next(self._VERSION)

        item = (version, cache)
        while version > self._cache[0]:
            self._cache = item

        return self._getCache(version)

    def getCache(self):
        u"Delayed access to the cache"
        return self._getCache(self._cache[0])

    cache   = property(lambda self: self.getCache, setCache)
    proc    = property(lambda self: self._proc)

class RunArgs:
    u"Arguments used for iterating"
    __slots__ = ('data', 'level', 'gen')
    def __init__(self, data):
        self.data  = data    # type: TrackData
        self.gen   = None    # type: Optional[TrackItems]
        self.level = 0

    def tolevel(self, proc):
        u"Changes a generator to fit the processor's level"
        if proc is None:
            return

        old  = self.level
        curr = proc.task.level.value
        gen  = self.gen

        if gen is None:
            return

        def collapse(gen):
            u"""
            Collapses items from *gen* into a series of *TrackItem*s
            each of which contain sequential items with similar parents
            """
            keyfcn = lambda i: i.parents
            yield from (TrackItems(data    = {fra.parents: fra for fra in grp},
                                   parents = key[:-1])
                        for key, grp in groupby(gen, key = keyfcn))

        def burst(gen):
            u"Transforms *gen* into *TrackItem*s, one per item in gen"
            yield from (TrackItems(data    = {key: frame},
                                   parents = frame.parents+(key,))
                        for frame in gen for key in frame)

        while old is not curr:
            gen  = collapse(gen) if old < curr else burst(gen)
            old += 1             if old < curr else -1

        self.gen   = gen
        self.level = curr

    @classmethod
    def checkClosure(cls, fcn):
        u"""
        We want the closure to be frozen.

        In this way, changing the task after implementing the iteration
        should have no effect.
        """
        closure = getattr(fcn, '__closure__', None)
        if closure is None:
            return

        for cell in closure:
            if isinstance(cell.cell_contents, Task):
                raise MemoryError("No including the task itself in the closure!")
            cls.checkClosure(cell.cell_contents)

    def apply(self, fcn, *_, level = None):
        u"Applies a function to generator's output"
        self.tolevel(level)
        if fcn is None:
            pass
        elif hasattr(fcn, '__iter__'):
            self.gen = fcn
        elif callable(fcn):
            self.checkClosure(fcn)
            gen      = self.gen
            self.gen = iter(fcn(frame) for frame in gen)
        else:
            raise NotImplementedError("What to do with " + str(fcn) + "?")

    first = property(lambda self: self.data.first)

class TrackData:
    u"Contains the track and task-created data"
    __slots__ = ('_cache', '_order')
    def __init__(self, order = None) -> None:
        self._order = [] if order is None else order # type: List

    def index(self, tsk) -> int:
        u"returns the index of the provided task"
        if tsk is None:
            return 0
        elif isinstance(tsk, int):
            return tsk
        else:
            return next(i for i, opt in enumerate(self._order) if opt.isitem(tsk))

    @property
    def first(self):
        u"returns the data from the first task"
        return self._order[0].getCache()

    def last(self, tsk):
        u"returns the data from the last task"
        return self._order[self.index(tsk)].getCache()

    def run(self, tsk = None):
        u"""
        Iterates through the list up to and including *tsk*.
        Iterates through all if *tsk* is None
        """
        args = RunArgs(self)
        ind  = len(self._order) if tsk is None else self.index(tsk)+1

        for item in self._order[:ind]:
            item.proc.run(args)
        return args.gen

    def append(self, proc):
        u"appends a processor"
        self._order.append(CacheItem(proc))

    def insert(self, index, proc):
        u"inserts a processor"
        self._order.insert(index, CacheItem(proc))
        self.delCache(index)

    def remove(self, ide):
        u"removes a processor"
        ind = self.index(ide)
        self.delCache(ind)
        self._order.pop(ind)

    def getCache(self, ide):
        u"access to processor's cache"
        return self._order[self.index(ide)].getCache()

    def setCacheDefault(self, ide, item):
        u"""
        Sets the cache unless, it exists already.
        If the item is a lambda, the latter is executed before storing
        """
        return self._order[self.index(ide)].setCacheDefault(item)

    def setCache(self, ide, value):
        u"sets a processor's cache"
        return self._order[self.index(ide)].setCache(value)

    def delCache(self, tsk = None):
        u"""
        Clears cache starting at *tsk*.
        Clears all if tsk is None
        """
        ind  = self.index(tsk)
        orig = self._order[ind]

        def _clear(proc, *_1):
            proc.setCache(None)

        for proc in self._order[ind:]:
            getattr(type(proc), 'clear', _clear)(proc, self, orig)

class TaskPair:
    u"data and model for tasks"
    __slots__ = ('model', 'data')
    def __init__(self):
        self.model = []
        self.data  = TrackData()

    def task(self, task:Union[Task,int,type], noemission = False) -> Task:
        u"returns a task"
        tsk = None
        if isinstance(task, Task):
            tsk = task

        elif isinstance(task, int):
            tsk = self.model[task]

        elif isinstance(task, type):
            try:
                tsk = next(i for i in self.model if isinstance(i, task))
            except StopIteration:
                pass

        if tsk is None and noemission:
            raise NoEmission()
        return tsk

    def add(self, task, proctype, index = None):
        u"adds a task to the list"
        TaskIsUniqueError.verify(task, self.model)
        proc = proctype(task)

        if index is None:
            self.model.append(task)
            self.data .append(proc)
        else:
            self.model.insert(index, task)
            self.data .insert(index, proc)

    def remove(self, task):
        u"removes a task from the list"
        if isinstance(task, int):
            self.model.remove(self.model[task])
        else:
            self.model.remove(task)

        self.data .remove(task)

    def update(self, tsk):
        u"clears data starting at *tsk*"
        self.data.delCache(tsk)

    def clear(self):
        u"clears data starting at *tsk*"
        self.data.clear()

class TaskControler(Controler):
    u"Data controler class"
    _PROCESSORS = dict()      # type: Dict[Task,Any]
    def __init__(self):
        self._items = dict()  # type: Dict[TrackReaderTask, TaskPair]
        if len(self._PROCESSORS) == 0:
            self.register()

    def task(self,
             parent : TrackReaderTask,
             task   : Union[Task,int,type],
             noemission = False) -> Task:
        u"returns a task"
        return self._items[parent].task(task, noemission = noemission)

    @property
    def tasktree(self) -> 'Iterator[Iterator[Task]]':
        u"Returns a data object in memory."
        yield from (iter(ite.model for ite in self._items.values()))

    def tasks(self, task:TrackReaderTask) -> 'Iterator[Task]':
        u"Returns a data object in memory."
        return iter(self._items[task].model)

    def cache(self, parent:TrackReaderTask, tsk:Optional[Task]):
        u"Returns the cache for a given task"
        return self._items[parent].data.getCache(tsk)

    def run(self, parent:TrackReaderTask, tsk:Optional[Task]):
        u"""
        Iterates through the list up to and including *tsk*.
        Iterates through all if *tsk* is None
        """
        return self._items[parent].data.run(tsk)

    @Controler.emit(returns = Controler.outasdict)
    def openTrack(self, task:TrackReaderTask, model = tuple()):
        u"opens a new file"
        pair  = TaskPair()
        tasks = (model if len(model) else (task,))
        for other in tasks:
            pair.add(other, self._PROCESSORS[type(other)])

        self._items[task] = pair
        return dict(controler = self, model = tasks)

    @Controler.emit(returns = Controler.outasdict)
    def closeTrack(self, task:TrackReaderTask):
        u"opens a new file"
        old = tuple(self._items[task].model)
        del self._items[task]
        return dict(controler = self, task = task, model = old)

    @Controler.emit(returns = Controler.outasdict)
    def addTask(self, parent:TrackReaderTask, task:Task, index = None):
        u"opens a new file"
        old = tuple(self._items[parent].model)
        self._items[parent].add(task, self._PROCESSORS[type(task)], index = index)
        return dict(controler = self, parent = parent, task = task, old = old)

    @Controler.emit(returns = Controler.outasdict)
    def updateTask(self, parent:TrackReaderTask, task:Union[Task,int,type], **kwargs):
        u"updates a task"
        tsk = self.task(parent, task, noemission = True)
        old = Controler.updateModel(tsk, **kwargs)
        self._items[parent].update(tsk)
        return dict(controler = self, parent = parent, task = tsk, old = old)

    @Controler.emit(returns = Controler.outasdict)
    def removeTask(self, parent:TrackReaderTask, task:Union[Task,int,type]):
        u"removes a task"
        tsk = self.task(parent, task, noemission = True)
        old = tuple(self._items[parent].model)
        self._items[parent].remove(tsk)
        return dict(controler = self, parent = parent, task = tsk, old = old)

    @Controler.emit
    def clearData(self, parent:'Optional[TrackReaderTask]' = None):
        "clears all data"
        if parent is None:
            self._data.clear()
        else:
            self._data[parent].clear()

    @classmethod
    def register(cls, processor = None):
        u"registers a task processor"
        from .processor import Processor
        if processor is None:
            processor = Processor

        cls._PROCESSORS[processor.tasktype] = processor
        for sclass in processor.__subclasses__():
            cls.register(sclass)
