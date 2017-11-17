#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Storing global properties"
from    typing      import Generic, TypeVar, Type, Iterator
import  inspect

_m_none = type('_m_none', (), {}) # pylint: disable=invalid-name
T       = TypeVar('T')

delete    = type('delete', tuple(), dict())    # pylint: disable=invalid-name

def getglobalsproperties(cls:Type[T], obj) -> Iterator[T]:
    "iterates over properties"
    pred = lambda i: isinstance(i, cls)
    yield from (i for _, i in inspect.getmembers(type(obj), pred))

class ConfigRootProperty(Generic[T]):
    "a property which links to the config"
    OBSERVERS = ('config.root',)
    def __init__(self, key:str) -> None:
        self.key = key

    def setdefault(self, obj, value:T, items:dict = None, **kwa):
        "initializes the property stores"
        if items is not None:
            kwa.update(**items)
        obj.config.root[self.key].default  = value
        obj.config.root[self.key].defaults = kwa

    def __get__(self, obj, tpe) -> T:
        return self if obj is None else obj.config.root[self.key].get()

    def __set__(self, obj, val:T) -> T:
        return self if obj is None else obj.config.root[self.key].set(val)

class ProjectRootProperty(Generic[T]):
    "a property which links to the project"
    OBSERVERS = ('project.root',)
    def __init__(self, key:str) -> None:
        self.key = key

    def setdefault(self, obj, value:T, items:dict = None, **kwa):
        "initializes the property stores"
        if items is not None:
            kwa.update(**items)
        obj.project.root[self.key].default  = value
        obj.project.root[self.key].defaults = kwa

    def __get__(self, obj, tpe) -> T:
        return self if obj is None else obj.project.root[self.key].get()

    def __set__(self, obj, val:T) -> T:
        return self if obj is None else obj.project.root[self.key].set(val)

class ConfigProperty(Generic[T]):
    "a property which links to the root config"
    OBSERVERS = ('config',)
    def __init__(self, key:str) -> None:
        self.key = key

    def setdefault(self, obj, value:T, items:dict = None, **kwa):
        "initializes the property stores"
        if items is not None:
            kwa.update(**items)
        obj.config[self.key].default  = value
        obj.config[self.key].defaults = kwa

    def __get__(self, obj, tpe) -> T:
        return self if obj is None else obj.config[self.key].get()

    def __set__(self, obj, val:T) -> T:
        return obj.config[self.key].set(val)

class BeadProperty(Generic[T]):
    "a property which links to the config and the project"
    OBSERVERS = 'config', 'project'
    def __init__(self, key:str) -> None:
        self.key = key

    def setdefault(self, obj, value:T, items:dict = None, **kwa):
        "initializes the property stores"
        if items is not None:
            kwa.update(**items)
        obj.project[self.key].default = None
        obj.project[self.key].set({})
        obj.config[self.key].default  = value
        obj.config[self.key].defaults = kwa

    @classmethod
    def clear(cls, obj):
        "clears the property stores"
        for prop in getglobalsproperties(cls, obj):
            obj.project[getattr(prop, 'key')].get().clear()

    def __get__(self, obj, tpe) -> T:
        if obj is None:
            return self # type: ignore
        value = obj.project[self.key].get().get(obj.bead, _m_none)
        if value is not _m_none:
            return value
        return obj.config[self.key].get()

    def __set__(self, obj, val:T) -> T:
        cache = dict(obj.project[self.key].get())
        if val == obj.config[self.key].get():
            cache.pop(obj.bead, None)
        else:
            cache[obj.bead] = val

        obj.project[self.key].set(cache)
        return val
