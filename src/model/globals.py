#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Utils for easily  with the JS side of the view"
from    typing      import (Generic, TypeVar, Type, # pylint: disable=unused-import
                            Iterator, Optional, Sequence, Union, Any)
from    collections import ChainMap
import  inspect


_CNT    = 2
_m_none = type('_m_none', (), {}) # pylint: disable=invalid-name
T       = TypeVar('T')

class GlobalsChild(ChainMap):
    "The main model"
    __NAME    = 'の'
    __slots__ = '__name'
    def __init__(self, name:str, parent: Optional['GlobalsChild'] = None) -> None:
        maps = tuple(dict() for i in range(_CNT)) # type: Sequence[Union[dict,GlobalsChild]]
        if parent is not None:
            maps += (parent,) # type: ignore

        self.__name = name # type: str
        super().__init__(*maps)

    @property
    def name(self) -> str:
        "returns the name"
        return self.__name

    def __getstate__(self):
        info = {self.__NAME: self.__name}
        info.update(self.maps[0])
        return info

    def __setstate__(self, info):
        self.__name = info.pop(self.__NAME)
        self.maps[0].update(info)

def getglobalsproperties(cls:Type[T], obj) -> Iterator[T]:
    "iterates over properties"
    pred = lambda i: isinstance(i, cls)
    yield from (i for _, i in inspect.getmembers(type(obj), pred))

class ConfigRootProperty(Generic[T]):
    "a property which links to the config"
    OBSERVERS = 'config.root',
    def __init__(self, key:str) -> None:
        self.key = key

    def setdefault(self, obj, value:T, items:Optional[dict] = None, **kwa):
        "initializes the property stores"
        if items is not None:
            kwa.update(**items)
        obj.config.root[self.key].default  = value
        obj.config.root[self.key].defaults = kwa

    def __get__(self, obj, tpe) -> T:
        return self if obj is None else obj.config.root[self.key].get()

    def __set__(self, obj, val:T) -> T:
        return self if obj is None else obj.config.root[self.key].set(val)

class ConfigProperty(Generic[T]):
    "a property which links to the root config"
    OBSERVERS = 'config',
    def __init__(self, key:str) -> None:
        self.key = key

    def setdefault(self, obj, value:T, items:Optional[dict] = None, **kwa):
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

    def setdefault(self, obj, value:T, items:Optional[dict] = None, **kwa):
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
            obj.project[prop.key].get().clear()

    def __get__(self, obj, tpe) -> T:
        if obj is None:
            return self # type: ignore
        value = obj.project[self.key].get().get(obj.bead, _m_none)
        if value is not _m_none:
            return value
        return obj.config[self.key].get()

    def __set__(self, obj, val:T) -> T:
        cache = obj.project[self.key].get()
        if val == obj.config[self.key].get():
            cache.pop(obj.bead, None)
        else:
            cache[obj.bead] = val
        return val

class _GlobalsAccess:
    def __init__(self, ctrl, key, name):
        self._ctrl = ctrl
        self._name = name
        self._key  = key

    def __getattr__(self, key):
        if key[0] == '_':
            return super().__getattribute__(key)
        if key == 'root':
            return self._ctrl.getGlobal(self._name)
        elif key == 'plot':
            return self._ctrl.getGlobal(self._name+'.plot')
        else:
            ctrl = self._ctrl.getGlobal(self._name+self._key)
            return getattr(ctrl, key)

    __getitem__ = __getattr__

    def __setattr__(self, key, val):
        if key[0] == '_':
            return super().__setattr__(key, val)
        ctrl = self._ctrl.getGlobal(self._name+self._key)
        return setattr(ctrl, key, val)

    __setitem__ = __setattr__

class GlobalsAccess:
    "Contains all access to model items likely to be set by user actions"
    def __init__(self, ctrl, key:Optional[str] = None, **_) -> None:
        self.__ctrl = getattr(ctrl, '_GlobalsAccess__ctrl', ctrl) # type: Any
        self.__key  = getattr(ctrl, '_GlobalsAccess__key',  key)  # type: Optional[str]

    @property
    def config(self):
        "returns an access to config"
        return _GlobalsAccess(self.__ctrl, self.__key, 'config')

    @property
    def css(self):
        "returns an access to css"
        return _GlobalsAccess(self.__ctrl, self.__key, 'css')

    @property
    def project(self):
        "returns an access to project"
        return _GlobalsAccess(self.__ctrl, self.__key, 'project')
