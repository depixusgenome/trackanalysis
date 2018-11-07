#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"List of processes and cache"
from typing         import (Union, Iterable, Sized, List, Tuple, Any, Iterator,
                            Type, cast)
from utils          import isfunction
from model.task     import Task
from .base          import Processor, register

def _version():
    i = 0
    while True:
        i = i+1
        yield i

class CacheItem:
    "Holds cache and its version"
    __slots__ = ('_proc', '_cache')
    _VERSION  = _version()
    def __init__(self,
                 proc:  Union['CacheItem', Processor],
                 cache: Tuple[int, Any] = (0, None)) -> None:
        self._proc  = cast(Processor,       getattr(proc, '_proc', proc))
        self._cache = cast(Tuple[int, Any], getattr(proc, '_cache', cache))

    def __getstate__(self):
        return {'proc': (type(self._proc), self._proc.task)}

    def __setstate__(self, values):
        self.__init__(values['proc'][0](values['proc'][1]))

    def isitem(self, tsk) -> bool:
        "returns the index of the provided task"
        return tsk is self.proc or tsk is self.proc.task

    def _getCache(self, old):
        "Delayed access to the cache"
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
        "Sets the cache and its version"
        if version is None:
            version = next(self._VERSION)

        item = (version, cache)
        while version > self._cache[0]:
            self._cache = item

        return self._getCache(version)

    def getCache(self):
        "Delayed access to the cache"
        return self._getCache(self._cache[0])

    cache   = property(lambda self: self.getCache(), setCache)
    proc    = property(lambda self: self._proc)

REP_T = Tuple[int, Processor, Processor] # pylint: disable=invalid-name
class CacheReplacement:
    """
    Context for replacing processors but keeping their cache
    """
    def __init__(self, cache: 'Cache', *options: Type[Processor]) -> None:
        self.options:  Tuple[Type[Processor],...] = options
        self.replaced: List[REP_T]                = []
        self.cache:    Cache                      = cache

    def taskcache(self, task:Task):
        "returns the task cache"
        return self.cache.getCache(task)()

    def __enter__(self):
        if self.cache is None:
            return None

        self.replaced.clear()
        if len(self.options) == 0:
            return self.cache

        reg  = register(self.options, force = True, recursive = False)
        itms = getattr(self.cache, '_items')
        for i, j in enumerate(self.cache):
            val = reg.get(type(j.task), None)
            if val is not None:
                self.replaced.append(cast(REP_T, (i, val(task = j.task), j)))
                setattr(itms[i], '_proc', self.replaced[-1][1])
        return self.cache

    def __exit__(self, *_):
        if self.cache is None:
            return

        itms = getattr(self.cache, '_items')
        for i, _, j in self.replaced:
            setattr(itms[i], '_proc', j)

class Cache(Iterable[Processor], Sized):
    "Contains the track and task-created data"
    __slots__ = ('_items',)
    def __init__(self, order: Iterable[Union[CacheItem, Processor, Task]] = None) -> None:
        if order is None:
            self._items: List[CacheItem] = []
        else:
            order       = list(order) # make sure order is not an iterator
            procs       = register() if any(isinstance(i, Task) for i in order) else {}
            self._items = [i            if isinstance(i, CacheItem) else
                           CacheItem(i) if isinstance(i, Processor) else
                           CacheItem(procs[type(i)](task = i))
                           for i in order]

    def index(self, tsk) -> int:
        "returns the index of the provided task"
        if isinstance(tsk, type) and issubclass(tsk, Task):
            # pylint: disable=unidiomatic-typecheck
            good = [i for i, j in enumerate(self._items) if type(j.proc.task) is tsk]
            if len(good) > 1:
                raise IndexError("ambiguous: please specify the task instance")
            elif len(good) == 0:
                raise IndexError("Missing task")
            return good[0]

        return (0       if tsk is None          else
                tsk     if isinstance(tsk, int) else
                next(i for i, j in enumerate(self._items) if j.isitem(tsk)))

    @property
    def model(self):
        "returns the data from the first task"
        yield from (i.proc.task for i in self._items)

    @property
    def first(self):
        "returns the data from the first task"
        return self._items[0].getCache()

    def last(self, tsk):
        "returns the data from the last task"
        return self._items[self.index(tsk)].getCache()

    def append(self, proc) -> 'Cache':
        "appends a processor"
        self._items.append(CacheItem(proc))
        return self

    def extend(self, procs):
        "appends processors"
        self._items.extend(CacheItem(i) for i in procs)
        return self

    def insert(self, index, proc):
        "inserts a processor"
        self._items.insert(index, CacheItem(proc))
        self.delCache(index)

    def pop(self, ide):
        "removes a processor"
        ind = self.index(ide)
        self.delCache(ind)
        self._items.pop(ind)
    remove = pop

    def keepupto(self, task) -> 'Cache':
        "returns a Cache with tasks up to and including *task*"
        if task is None or task is Ellipsis:
            return Cache(self._items)
        return Cache(self._items[:self.index(task)+1])

    def cleancopy(self) -> 'Cache':
        "returns a cache with only the processors"
        return Cache([i.proc for i in self._items])

    def getCache(self, ide):
        "access to processor's cache"
        return self._items[self.index(ide)].getCache()

    def setCacheDefault(self, ide, item):
        """
        Sets the cache unless, it exists already.
        If the item is a lambda, the latter is executed before storing
        """
        return self._items[self.index(ide)].setCacheDefault(item)

    def setCache(self, ide, value):
        "sets a processor's cache"
        return self._items[self.index(ide)].setCache(value)

    def delCache(self, tsk = None):
        """
        Clears cache starting at *tsk*.
        Clears all if tsk is None
        """
        ind  = self.index(tsk)
        orig = self._items[ind]

        def _clear(proc, *_1):
            proc.setCache(None)

        for proc in self._items[ind:]:
            getattr(type(proc), 'clear', _clear)(proc, self, orig)

    def __len__(self):
        return len(self._items)

    def __iter__(self) -> Iterator[Processor]:
        yield from (i.proc for i in self._items)

    def items(self) -> Iterator[CacheItem]:
        "yields processors and caches"
        return iter(self._items)

    def __contains__(self, tsk:type):
        return any(tsk is i or tsk is i.tasktype for i in self)

    def __getitem__(self, ide):
        if isinstance(ide, slice):
            start = None if ide.start is None else self.index(ide.start)
            stop  = None if ide.stop  is None else self.index(ide.stop)
            if ide.step not in (None, 1):
                raise NotImplementedError("Slicing a list of tasks?")

            return iter(item.proc for item in self._items[slice(start, stop)])
        return self._items[self.index(ide)]
