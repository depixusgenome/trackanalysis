#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"List of processes and cache"
from .base          import Processor # pylint: disable=unused-import
from utils          import isfunction

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

class Cache:
    u"Contains the track and task-created data"
    __slots__ = ('_items',)
    def __init__(self, order = None) -> None:
        self._items = [] if order is None else order # type List[CacheItem]

    def index(self, tsk) -> int:
        u"returns the index of the provided task"
        if tsk is None:
            return 0
        elif isinstance(tsk, int):
            return tsk
        else:
            return next(i for i, opt in enumerate(self._items) if opt.isitem(tsk))

    @property
    def first(self):
        u"returns the data from the first task"
        return self._items[0].getCache()

    def last(self, tsk):
        u"returns the data from the last task"
        return self._items[self.index(tsk)].getCache()

    def append(self, proc):
        u"appends a processor"
        self._items.append(CacheItem(proc))

    def insert(self, index, proc):
        u"inserts a processor"
        self._items.insert(index, CacheItem(proc))
        self.delCache(index)

    def pop(self, ide):
        u"removes a processor"
        ind = self.index(ide)
        self.delCache(ind)
        self._items.pop(ind)

    remove = pop

    def getCache(self, ide):
        u"access to processor's cache"
        return self._items[self.index(ide)].getCache()

    def setCacheDefault(self, ide, item):
        u"""
        Sets the cache unless, it exists already.
        If the item is a lambda, the latter is executed before storing
        """
        return self._items[self.index(ide)].setCacheDefault(item)

    def setCache(self, ide, value):
        u"sets a processor's cache"
        return self._items[self.index(ide)].setCache(value)

    def delCache(self, tsk = None):
        u"""
        Clears cache starting at *tsk*.
        Clears all if tsk is None
        """
        ind  = self.index(tsk)
        orig = self._items[ind]

        def _clear(proc, *_1):
            proc.setCache(None)

        for proc in self._items[ind:]:
            getattr(type(proc), 'clear', _clear)(proc, self, orig)

    def __getitem__(self, ide):
        if isinstance(ide, slice):
            start = None if ide.start is None else self.index(ide.start)
            stop  = None if ide.stop  is None else self.index(ide.stop)
            if ide.step not in (None, 1):
                raise NotImplementedError("Slicing a list of tasks?")

            return iter(item.proc for item in self._items[slice(start, stop)])
        else:
            return self._items[self.index(ide)]
