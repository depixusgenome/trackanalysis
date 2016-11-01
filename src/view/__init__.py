#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"basic view module"
from typing         import Optional, Dict, Callable # pylint: disable=unused-import

from flexx          import ui

from control.event  import Controller

class View:
    u"Classes to be passed a controller"
    _ctrl = None    # type: Controller
    _keys = dict()  # type: Dict[str,Callable]
    def unobserve(self):
        u"Removes the controller"
        if '_ctrl' in self.__dict__:
            self._ctrl.unobserve()
            del self._ctrl

        children   = list(getattr(self, 'children', []))
        while len(children):
            cur = children.pop()
            if isinstance(cur, View):
                cur.unobserve()
            else:
                children.extend(getattr(cur, 'children', []))

    def connect(self, *_1, **_2):
        u"Should be implemetented by flexx.ui.Widget"
        raise NotImplementedError("View should derive from a flexx app")

    def observe(self, ctrl:Controller):
        u"Sets up the controller"
        if '_ctrl' not in self.__dict__:
            self._ctrl = ctrl
            self.addKeyPress()
            self.connect("key_press", self.__onKeyPress)

        children   = list(getattr(self, 'children', []))
        while len(children):
            cur = children.pop()
            if isinstance(cur, View):
                cur.observe(ctrl)
            else:
                children.extend(getattr(cur, 'children', []))

    def __onKeyPress(self, *evt):
        if len(evt) != 1:
            return

        cur = '-'.join(evt[0].modifiers)+'-'+evt[0].key
        for name, fcn in self._keys.items():
            if cur == self._ctrl.getConfig("keypress."+name):
                fcn()
                break

    def addKeyPress(self, *args, **keys):
        u"sets-up keypress methods"
        keys.update(args)
        self._keys.update(keys)

    def popKeyPress(self, *args):
        u"removes keypress method"
        if '_keys' not in self.__dict__:
            return

        elif len(args) == 1 and args[0] is all:
            self._keys = dict()

        else:
            for arg in args:
                self._keys.pop(arg, None)


    def button(self, fcn:Callable, keypress:str, **kwa):
        u"creates and connects a button"
        if 'text' not in kwa:
            kwa['text'] = '<u>{}</u>{}'.format(keypress[0].upper(), keypress[1:])

        btn = ui.Button(**kwa)
        btn.connect('mouse_down', fcn)
        self.addKeyPress((keypress, fcn))
