#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"controls keypress actions"
from typing                 import Callable, Dict
from bokeh.core.properties  import String, Int, List
from bokeh.model            import Model
from control.action         import Action

class KeyStrokes(dict):
    """
    Model for key bindings
    """
    name = 'keystroke'

class KeyCalls(dict):
    """
    Model for key bindings
    """
    name = 'keystroke'

class DpxKeyEvent(Model):
    "controls keypress actions"
    keys               = List(String)
    value              = String("")
    count              = Int(0)
    __implementation__ = "keypress.coffee"
    def __init__(self, ctrl = None):
        super().__init__()
        self._keys:     Dict[str, str]      = KeyCalls()
        self._bindings: Dict[str, Callable] = KeyStrokes()
        if ctrl is not None:
            self.observe(ctrl)

    def close(self):
        "Removes the controller"
        self._keys.clear()
        self._keys     = KeyCalls()
        self._bindings = KeyStrokes()

    def __contains__(self, val):
        return val in self._bindings.values() and val in self.keys

    def _setkeys(self):
        self.keys = [self._bindings[name] for name in self._keys]

    def _onkeypress(self, ctrl, **_):
        "Method to be connected to the gui"
        name, fcn = tuple(self._keys.items())[self.keys.index(self.value)]
        with Action(ctrl, calls = name):
            fcn()

    def observe(self, ctrl):
        "observe the controller"
        if self._bindings not in ctrl.theme:
            fcn = lambda **_: self._setkeys()
            ctrl.theme  .add    (self._bindings)
            ctrl.theme  .observe(self._bindings, fcn)
            ctrl.display.add    (self._keys)
            ctrl.display.observe(self._keys,     fcn)
        self._setkeys()

    def addtodoc(self, ctrl, doc):
        "returns object root"
        self.on_change("count", lambda attr, old, value: self._onkeypress(ctrl))
        self._setkeys()
        doc.add_root(self)
