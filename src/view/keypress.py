#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"controls keypress actions"
from typing import Callable, Optional # pylint: disable=unused-import

class KeyPressManager:
    u"controls keypress actions"
    def __init__(self, **kwargs):
        self._keys = kwargs.get('keys', dict()) # type: Dict[str,Callable]
        self._ctrl = kwargs.get('ctrl', None)   # type: Optional[Controller]

    def observe(self, ctrl, **kwargs):
        u"Sets-up the controller"
        self._ctrl = ctrl
        self.addKeyPress(**kwargs)

    def unobserve(self):
        u"Removes the controller"
        self.popKeyPress(all)
        del self._ctrl

    def onKeyPress(self, *evt):
        u"Method to be connected to the gui"
        if len(evt) != 1 or len(self._keys) == 0:
            return

        cur   = '-'.join(evt[0].modifiers)+'-'+evt[0].key
        items = self._ctrl.getGlobal('config')
        for name, fcn in self._keys.items():
            if cur == items.get(name):
                fcn()
                break

    def addKeyPress(self, *args, **keys):
        u"sets-up keypress methods"
        keys.update(args)
        self._keys.update(keys)
        if not all(isinstance(i, Callable) for i in keys.values()) :
            raise TypeError("keypress values should be callable")

    def popKeyPress(self, *args):
        u"removes keypress method"
        if len(args) == 1 and args[0] is all:
            self._keys = dict()

        else:
            for arg in args:
                self._keys.pop(arg, None)
