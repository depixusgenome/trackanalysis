#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Storing global properties"
import  inspect

class ConfigRootProperty:
    "a property which links to the config"
    OBSERVERS = ('config.root',)
    def __init__(self, key:str) -> None:
        self.key = key

    def setdefault(self, obj, value, items:dict = None, **kwa):
        "initializes the property stores"
        if items is not None:
            kwa.update(**items)
        obj.config.root[self.key].default  = value
        obj.config.root[self.key].defaults = kwa

    def __get__(self, obj, tpe):
        return self if obj is None else obj.config.root[self.key].get()

    def __set__(self, obj, val):
        return self if obj is None else obj.config.root[self.key].set(val)

class ProjectRootProperty:
    "a property which links to the project"
    OBSERVERS = ('project.root',)
    def __init__(self, key:str) -> None:
        self.key = key

    def setdefault(self, obj, value, items:dict = None, **kwa):
        "initializes the property stores"
        if items is not None:
            kwa.update(**items)
        obj.project.root[self.key].default  = value
        obj.project.root[self.key].defaults = kwa

    def __get__(self, obj, tpe):
        return self if obj is None else obj.project.root[self.key].get()

    def __set__(self, obj, val):
        return self if obj is None else obj.project.root[self.key].set(val)

class ConfigProperty:
    "a property which links to the root config"
    OBSERVERS = ('config',)
    def __init__(self, key:str) -> None:
        self.key = key

    def setdefault(self, obj, value, items:dict = None, **kwa):
        "initializes the property stores"
        if items is not None:
            kwa.update(**items)
        obj.config[self.key].default  = value
        obj.config[self.key].defaults = kwa

    def __get__(self, obj, tpe):
        return self if obj is None else obj.config[self.key].get()

    def __set__(self, obj, val):
        return obj.config[self.key].set(val)

class BeadProperty:
    "a property which links to the config and the project"
    OBSERVERS = 'config', 'project'
    _NONE     = type('_NONE', (), {})

    def __init__(self, key:str) -> None:
        self.key = key

    def setdefault(self, obj, value, items:dict = None, **kwa):
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
        pred = lambda i: isinstance(i, cls)
        for _, prop in inspect.getmembers(type(obj), pred):
            obj.project[getattr(prop, 'key')].get().clear()

    def __get__(self, obj, tpe):
        if obj is None:
            return self # type: ignore
        value = obj.project[self.key].get().get(obj.bead, self._NONE)
        if value is not self._NONE:
            return value
        return obj.config[self.key].get()

    def __set__(self, obj, val):
        cache = dict(obj.project[self.key].get())
        if val == obj.config[self.key].get():
            cache.pop(obj.bead, None)
        else:
            cache[obj.bead] = val

        obj.project[self.key].set(cache)
        return val

def configroot(name: str) -> ConfigRootProperty:
    "returns a prop"
    return ConfigRootProperty(name)

def projectroot(name: str) -> ProjectRootProperty:
    "returns a prop"
    return ProjectRootProperty(name)

def config(name: str) -> ConfigProperty:
    "returns a prop"
    return ConfigProperty(name)

def bead(name: str) -> BeadProperty:
    "returns a prop"
    return BeadProperty(name)

__all__ = ['ConfigRootProperty', 'ProjectRootProperty', 'ConfigProperty', 'BeadProperty']
