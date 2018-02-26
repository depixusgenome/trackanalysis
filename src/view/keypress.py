#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"controls keypress actions"
from typing                 import Callable, Optional, Dict
from bokeh.core.properties  import String, Int, List
from bokeh.model            import Model
from control.action         import Action
from control.event          import Controller

class DpxKeyEvent(Model):
    u"controls keypress actions"
    keys               = List(String)
    value              = String("")
    count              = Int(0)
    __implementation__ = "keypress.coffee"

    def __init__(self, **kwargs):
        super().__init__()
        self._ctrl: Optional[Controller] = kwargs.pop('ctrl', None)
        self._keys: Dict[str,Callable]   = kwargs.pop('keys', dict())

    def __item(self, name):
        return getattr(self._ctrl, 'globals', self._ctrl).css[name].get()

    def close(self):
        u"Removes the controller"
        self._keys.clear()
        self._keys = dict()
        self._ctrl = None

    def _setkeys(self):
        self.keys = [self.__item(name) for name in self._keys]

    def onKeyPress(self):
        u"Method to be connected to the gui"
        name, fcn = tuple(self._keys.items())[self.keys.index(self.value)]
        with Action(self._ctrl, calls = name):
            fcn()

    def addKeyPress(self, *args, **kwargs):
        u"""
        Sets-up keypress methods.

        if args is one string, then that string is used as a prefix to all
        keys in kwargs.

        Otherwise args must be valid arguments to dict.update.
        """
        if len(args) == 1 and isinstance(args[0], str) and len(kwargs):
            kwargs = {args[0]+'.'+name: val for name, val in kwargs.items()}
        else:
            kwargs.update(args)

        if not all(callable(i) for i in kwargs.values()) :
            raise TypeError("keypress values should be callable: "+str(kwargs))
        self._keys.update(kwargs)
        self._setkeys()

    def popKeyPress(self, *args):
        u"removes keypress method"
        if len(args) == 1 and args[0] is all:
            self._keys.clear()
            self._keys = dict()

        else:
            for arg in args:
                self._keys.pop(arg, None)
        self._setkeys()

    def getroots(self, doc):
        u"returns object root"
        self.on_change("count", lambda attr, old, value: self.onKeyPress())
        doc.add_root(self)
        return self,

KeyPressManager = DpxKeyEvent
