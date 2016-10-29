#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"""
All things global:
    - current track
    - current task
    - current view ...
"""
from collections    import namedtuple, ChainMap
from .event         import Controller, NoEmission

ReturnPair = namedtuple('ReturnPair', ['old', 'value'])
_empty     = type('_None', tuple(), dict())
class GlobalsController(Controller):
    u"Data controller class"
    def __init__(self):
        super().__init__()
        self.__defaults = {"keypress.undo": "Ctrl-z",
                           "keypress.redo": "Ctrl-y"}
        self.__config   = ChainMap(dict(), self.__defaults)
        self.__project  = {}

    @staticmethod
    def __update(items, args, kwargs):
        kwargs.update(args)
        ret = dict(empty = _empty)
        for key, val in kwargs.items():
            old = items.get(key, _empty)
            if val is _empty:
                items.pop(key, None)
            else:
                items[key] = val

            if old != val:
                ret[key] = ReturnPair(old, val)

        if len(ret):
            return ret
        else:
            raise NoEmission()

    @staticmethod
    def __get(items, keys, default = _empty):
        u"returns values associated to the keys"
        if default is not _empty:
            if len(keys) == 1:
                return items.get(keys[0], default)
            return iter(items.get(key, val) for key, val in zip(keys, default))
        else:
            if len(keys) == 1:
                return items[keys[0]]
            return iter(items[key] for key in keys)

    @Controller.emit(returns = Controller.outasdict)
    def updateGlobal(self, *args, **kwargs):
        u"updates view information"
        return self.__update(self.__project, args, kwargs)

    @Controller.emit(returns = Controller.outasdict)
    def updateConfig(self, *args, **kwargs):
        u"updates view information"
        return self.__update(self.__config, args, kwargs)

    def deleteGlobal(self, *key):
        u"removes view information"
        return self.updateGlobal(**dict.fromkeys(key, _empty))

    def deleteConfig(self, *key):
        u"removes view information"
        return self.updateConfig(**dict.fromkeys(key, _empty))

    def getGlobal(self, *keys, default = _empty):
        u"returns values associated to the keys"
        return self.__get(self.__project, keys, default)

    def getConfig(self, *keys, default = _empty):
        u"returns values associated to the keys"
        return self.__get(self.__config, keys, default)
