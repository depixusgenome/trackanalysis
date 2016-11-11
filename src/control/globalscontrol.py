#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"""
All things global:
    - current track
    - current task
    - current view ...

A global map can be added by any view, although one should take care not
to mix both project-specific and project-generic info. For example, there
are different maps for storing the key mappings from the current track being
displayed.

Maps default values are memorized. The user can change the values then return
to the default settings. It is also possible to configure a map to hold
default, loaded (saved from a previous session) and current values.

A child map is a specialization of a parent map. It is specidied using a key
with "parent.child". A child map has access to all parent items. It can overload
the values but cannot change the parent's.

Such a parent/child relationship can be used to specialize default values. For
example, the "plot" map will contain items for all plot types. The "plot.bead"
map only needs specify those default values that should be changed for this type
of plot.
"""
from typing         import Dict, Union          # pylint: disable=unused-import
from collections    import namedtuple, ChainMap
from .event         import Controller

ReturnPair = namedtuple('ReturnPair', ['old', 'value'])
delete     = type('delete', tuple(), dict())    # pylint: disable=invalid-name

class DefaultsMap(Controller):
    u"Dictionnary with defaults values. It can be reset to these."
    def __init__(self, name, cnt = 2, maps = None, **kwargs):
        super().__init__(**kwargs)
        self.__name  = name.replace('.', '')
        if maps is not None:
            self.__items = ChainMap(dict(), *maps)
        else:
            self.__items = ChainMap(*(dict() for i in range(cnt)))

    def createChild(self, name, **kwargs):
        u"returns a child map"
        return DefaultsMap(name, maps = self.__items.maps, **kwargs)

    def setdefaults(self, *args, version = None, **kwargs):
        u"adds defaults to the config"
        if len(args) == 1 and isinstance(args[0], dict):
            kwargs.update(*args)
        else:
            kwargs.update(args)

        if version is None:
            version = -1
        self.__items.maps[version].update(**kwargs)

    def reset(self, version = None):
        u"resets to default values"
        if version is None:
            version = -1
        for i in range(version):
            self.__items.maps[i].clear()

    def update(self, *args, **kwargs) -> dict:
        u"updates keys or raises NoEmission"
        if len(args) == 1 and isinstance(args[0], dict):
            kwargs.update(*args)
        else:
            kwargs.update(args)

        ret = dict(empty = delete) # type: Dict[str,Union[type,ReturnPair]]
        for key, val in kwargs.items():
            old = self.__items.get(key, delete)
            if val is delete:
                self.__items.pop(key, None)
            else:
                self.__items[key] = val

            if old != val:
                ret[key] = ReturnPair(old, val)

        if len(ret):
            return self.handle("update"+self.__name, self.outasdict, ret)

    def delete(self, *args):
        u"removes view information"
        return self.update(dict.fromkeys(args, delete))

    def get(self, *keys, default = delete):
        u"returns values associated to the keys"
        if default is not delete:
            if len(keys) == 1:
                return self.__items.get(keys[0], default)

            elif isinstance(default, list):
                return iter(self.__items.get(key, val) for key, val in zip(keys, default))

            else:
                return iter(self.__items.get(key, default) for key in keys)
        else:
            if len(keys) == 1:
                return self.__items[keys[0]]
            return iter(self.__items[key] for key in keys)

class GlobalsController(Controller):
    u"Data controller class"
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.__maps = dict()
        self.addGlobalMap('config')
        self.addGlobalMap('plot',
                          panningspeed = .2,
                          zoomingspeed = .2,
                          tools        = 'xpan,wheel_zoom,box_zoom,reset,save')
        self.addGlobalMap('keypress',
                          undo = "Ctrl-z",
                          redo = "Ctrl-y",
                          open = "Ctrl-o",
                          save = "Ctrl-s",
                          quit = "Ctrl-q")

        self.addGlobalMap('current')

    def addGlobalMap(self, key, *args, **kwargs):
        u"adds a map"
        if '.' in key:
            parent = self.__maps[key[:key.rfind('.')]]
            self.__maps[key] = parent.createChild(key, handlers = self._handlers)
        else:
            self.__maps[key] = DefaultsMap(key, handlers = self._handlers)

        self.__maps[key].setdefaults(*args, **kwargs)

    def removeGlobalMap(self, key):
        u"removes a map"
        self.__maps.pop(key)

    def setGlobalDefaults(self, key, **kwargs):
        u"sets default values to the map"
        self.__maps[key].setdefaults(**kwargs)

    def updateGlobal(self, key, *args, **kwargs) -> dict:
        u"updates view information"
        return self.__maps[key].update(*args, **kwargs)

    def deleteGlobal(self, key, *args):
        u"removes view information"
        return self.__maps[key].delete(*args)

    def getGlobal(self, key, *args, default = delete):
        u"returns values associated to the keys"
        if len(args) == 0:
            return self.__maps[key]
        return self.__maps[key].get(*args, default = default)
