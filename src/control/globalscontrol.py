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

class DefaultsMapController(ChainMap):
    u"Dictionnary with defaults values. It can be reset to these."
    def __init__(self, cnt = 2):
        super().__init__(*(dict() for i in range(cnt)))

    def updateVersion(self, *args, version = None, **kwargs):
        u"adds defaults to the config"
        if version is None:
            version = -1
        self.maps[version].update(*args, **kwargs)

    def reset(self, version = None):
        u"resets to default values"
        if version is None:
            version = -1
        for i in range(version):
            self.maps[i].clear()

    def update(self, *args, **kwargs):
        u"updates keys or raises NoEmission"
        if len(args) == 1 and isinstance(args[0], dict):
            kwargs.update(*args)
        else:
            kwargs.update(args)

        ret = dict(empty = delete)
        for key, val in kwargs.items():
            old = super().get(key, delete)
            if val is delete:
                self.pop(key, None)
            else:
                self[key] = val

            if old != val:
                ret[key] = ReturnPair(old, val)
        if len(ret):
            return ret
        else:
            raise NoEmission("Config is unchanged")

    def get(self, keys, default = delete):
        u"returns values associated to the keys"
        if default is not delete:
            if len(keys) == 1:
                return super().get(keys[0], default)

            elif isinstance(default, list):
                return iter(super().get(key, val) for key, val in zip(keys, default))

            else:
                return iter(super().get(key, default) for key in keys)
        else:
            if len(keys) == 1:
                return self[keys[0]]
            return iter(self[key] for key in keys)

class GlobalsController(Controller):
    u"Data controller class"
    def __init__(self):
        super().__init__()
        self.__config   = DefaultsMapController()
        self.__config.updateVersion({"keypress.undo": "Ctrl-z",
                                     "keypress.redo": "Ctrl-y",
                                     "keypress.open": "Ctrl-o",
                                     "keypress.save": "Ctrl-s",
                                     "keypress.quit": "Ctrl-q"})
        self.__project  = DefaultsMapController()

    def updateConfigDefault(self, *args, version = None, **kwargs):
        u"adds defaults to the config"
        self.__config.updateVersion(*args, version = version, **kwargs)

    def updateProjectDefault(self, *args, version = None, **kwargs):
        u"adds defaults to the project"
        self.__project.updateVersion(*args, version = version, **kwargs)

    def resetConfig(self, *args, version = None, **kwargs):
        u"adds defaults to the config"
        self.__config.reset(*args, version = version, **kwargs)

    def resetProject(self, *args, version = None, **kwargs):
        u"adds defaults to the project"
        self.__project.reset(*args, version = version, **kwargs)

    @Controller.emit
    def updateGlobal(self, *args, **kwargs) -> dict:
        u"updates view information"
        return self.__project.update(*args, **kwargs)

    @Controller.emit
    def updateConfig(self, *args, **kwargs) -> dict:
        u"updates view information"
        return self.__config.update(*args, **kwargs)

    def deleteGlobal(self, *key):
        u"removes view information"
        return self.updateGlobal(**dict.fromkeys(key, delete))

    def deleteConfig(self, *key):
        u"removes view information"
        return self.updateConfig(**dict.fromkeys(key, delete))

    def getGlobal(self, *keys, default = delete):
        u"returns values associated to the keys"
        return self.__project.get(keys, default)

    def getConfig(self, *keys, default = delete):
        u"returns values associated to the keys"
        return self.__config.get(keys, default)
