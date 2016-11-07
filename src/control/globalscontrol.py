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
delete     = type('delete', tuple(), dict()) # pylint: disable=invalid-name
class GlobalsController(Controller):
    u"Data controller class"
    def __init__(self):
        super().__init__()
        self.__defaults = {
            "keypress.undo": "Ctrl-z",
            "keypress.redo": "Ctrl-y",
            "keypress.open": "Ctrl-o",
            "keypress.save": "Ctrl-s",
            "keypress.quit": "Ctrl-q",
            "plot.bead.tools"      : 'xpan,box_zoom,undo,redo,reset,save',
            "plot.bead.z.color"    : 'blue',
            "plot.bead.z.glyph"    : 'circle',
            "plot.bead.z.size"     : 1,
            "plot.bead.zmag.color" : 'red',
            "plot.bead.zmag.glyph" : 'line',
            "plot.bead.zmag.size"  : 1,
            }
        self.__config   = ChainMap(dict(), self.__defaults)
        self.__project  = {}

    @staticmethod
    def __update(items, args, kwargs):
        kwargs.update(args)
        ret = dict(empty = delete)
        for key, val in kwargs.items():
            old = items.get(key, delete)
            if val is delete:
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
    def __get(items, keys, default = delete):
        u"returns values associated to the keys"
        if default is not delete:
            if len(keys) == 1:
                return items.get(keys[0], default)
            return iter(items.get(key, val) for key, val in zip(keys, default))
        else:
            if len(keys) == 1:
                return items[keys[0]]
            return iter(items[key] for key in keys)

    @Controller.emit
    def updateGlobal(self, *args, **kwargs) -> dict:
        u"updates view information"
        return self.__update(self.__project, args, kwargs)

    @Controller.emit
    def updateConfig(self, *args, **kwargs) -> dict:
        u"updates view information"
        return self.__update(self.__config, args, kwargs)

    def deleteGlobal(self, *key):
        u"removes view information"
        return self.updateGlobal(**dict.fromkeys(key, delete))

    def deleteConfig(self, *key):
        u"removes view information"
        return self.updateConfig(**dict.fromkeys(key, delete))

    def getGlobal(self, *keys, default = delete):
        u"returns values associated to the keys"
        return self.__get(self.__project, keys, default)

    def getConfig(self, *keys, default = delete):
        u"returns values associated to the keys"
        return self.__get(self.__config, keys, default)
