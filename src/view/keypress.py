#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"controls keypress actions"
from typing                 import Callable, Dict
from bokeh.core.properties  import String, Int, List
from bokeh.model            import Model
from control.action         import Action

class KeyStrokes(Dict[str, str]):
    """
    Model for key bindings
    """
    NAME = 'keystroke'

class KeyCalls(Dict[str, Callable]):
    """
    Model for key bindings
    """
    NAME = 'keystroke'

class DpxKeyEvent(Model):
    "controls keypress actions"
    keys               = List(String)
    value              = String("")
    count              = Int(0)
    __implementation__ = "keypress.coffee"
    def __init__(self, ctrl = None):
        super().__init__()
        self._keys     = KeyCalls()
        self._bindings = KeyStrokes()
        if ctrl:
            self.addtocontroller(ctrl)

    def addtocontroller(self, ctrl):
        "adds models to the controller"
        ctrl.theme  .add(self._bindings)
        ctrl.display.add(self._keys)

    def close(self):
        "Removes the controller"
        self._keys.clear()
        self._keys     = KeyCalls()
        self._bindings = KeyStrokes()

    def _setkeys(self):
        self.keys = [self._bindings[name] for name in self._keys]

    def _onkeypress(self, ctrl):
        "Method to be connected to the gui"
        name, fcn = tuple(self._keys.items())[self.keys.index(self.value)]
        with Action(ctrl, calls = name):
            fcn()

    def observe(self, ctrl):
        "observe the controller"
        ctrl.theme  .observe(self._keys.NAME, lambda **_: self._setkeys())
        ctrl.display.observe(self._keys.NAME, lambda **_: self._setkeys())
        self._setkeys()

    def addtodoc(self, ctrl, doc):
        "returns object root"
        self.on_change("count", lambda attr, old, value: self._onkeypress(ctrl))
        self._setkeys()
        doc.add_root(self)
