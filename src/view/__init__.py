#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"basic view module"
from typing         import Optional     # pylint: disable=unused-import
from control.event  import Controller

class View:
    u"Classes to be passed a controller"
    _ctrl = None # type: Controller
    def setCtrl(self, ctrl:Controller):
        u"Sets up the controller"
        self._ctrl = ctrl
        children   = list(getattr(self, 'children', []))
        while len(children):
            cur = children.pop()
            if isinstance(cur, View):
                cur.setCtrl(ctrl)
            else:
                children.extend(getattr(cur, 'children', []))
