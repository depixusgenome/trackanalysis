#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Storing global properties"
from typing          import Dict

from utils.logconfig import getLogger
from ._child         import GlobalsChild, delete
from ._access        import SingleMapAccess
LOGS    = getLogger(__name__)

class Globals:
    """
    container for global values.
    These can be accessed using a main key and secondary keys:

    >> # Get the secondary key 'keypress.pan.x' in 'plot'
    >> ctrl.getGlobal('plot').keypress.pan.x.low.get()

    >> # Get the secondary keys 'keypress.pan.x.low' and 'high'
    >> ctrl.getGlobal('plot').keypress.pan.x.get('low', 'high')

    >> # Get secondary keys starting with 'keypress.pan.x'
    >> ctrl.getGlobal('plot').keypress.pan.x.items
    """
    def __init__(self, **_):
        self.__maps: Dict[str, GlobalsChild] = dict()

    def items(self):
        "access to all maps"
        return self.__maps.items()

    def addGlobalMap(self, key, *args, **kwargs):
        "adds a map"
        if key not in self.__maps:
            parent           = self.__maps[key[:key.rfind('.')]] if '.' in key else None
            self.__maps[key] = GlobalsChild(key, parent)

        self.__maps[key].setdefaults(*args, **kwargs)
        return SingleMapAccess(self.__maps[key], '')

    def removeGlobalMap(self, key):
        "removes a map"
        self.__maps.pop(key)

    def setGlobalDefaults(self, key, **kwargs):
        "sets default values to the map"
        self.__maps[key].setdefaults(**kwargs)

    def updateGlobal(self, key, *args, **kwargs) -> dict:
        "updates view information"
        return self.__maps[key].update(*args, **kwargs)

    def deleteGlobal(self, key, *args):
        "removes view information"
        return self.__maps[key].pop(*args)

    def getGlobal(self, key, *args, default = delete, model = False):
        "returns values associated to the keys"
        if key is Ellipsis:
            return self

        if len(args) == 0 or len(args) == 1 and args[0] == '':
            if model:
                return self.__maps[key]
            return SingleMapAccess(self.__maps[key], '')
        return self.__maps[key].get(*args, default = default)

__all__ = ['Globals']
