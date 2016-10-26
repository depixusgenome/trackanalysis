#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"""
All things global:
    - current track
    - current task
    - current view ...
"""
from collections    import namedtuple
from .event         import Controller, NoEmission

ReturnPair = namedtuple('ReturnPair', ['old', 'value'])
_empty     = type('_None', tuple(), dict())
class GlobalsController(Controller):
    u"Data controller class"
    def __init__(self):
        super().__init__()
        self._info = dict()

    @Controller.emit(returns = Controller.outasdict)
    def updateGlobal(self, **kwargs):
        u"updates view information"
        ret = dict(empty = _empty)
        for key, val in kwargs.items():
            old = self._info.get(key, _empty)
            if val is _empty:
                self._info.pop(key, None)
            else:
                self._info[key] = val

            if old != val:
                ret[key] = ReturnPair(old, val)

        if len(ret):
            return ret
        else:
            raise NoEmission()

    def deleteGlobal(self, *key):
        u"removes view information"
        return self.updateGlobal(self, **dict.fromkeys(key, _empty))

    def getGlobal(self, *keys):
        u"returns values associated to the keys"
        if len(keys) == 1:
            return self._info[keys[0]]
        return iter(self._info[key] for key in keys)
