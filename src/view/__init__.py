#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"basic view module"
from typing         import Optional     # pylint: disable=unused-import
from control.event  import Controler    # pylint: disable=unused-import

class View:
    u"Classes to be passed a controler"
    _ctrl = None # type: Controler
    def setCtrl(self, ctrl:Controler):
        u"Sets up the controler"
        self._ctrl = ctrl
        children   = list(getattr(self, 'children', []))
        while len(children):
            cur = children.pop()
            if isinstance(cur, View):
                cur.setCtrl(ctrl)
            else:
                children.extend(getattr(cur, 'children', []))
