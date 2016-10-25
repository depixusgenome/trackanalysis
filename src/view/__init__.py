#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"basic view module"
from typing         import Optional     # pylint: disable=unused-import
from control.event  import Controler    # pylint: disable=unused-import

class View:
    u"Classes to be passed a controler"
    def __init__(self):
        self._ctrl = None # type: Optional[Controler]

    def setCtrl(self, ctrl:Controler):
        u"Sets up the controler"
        children = [self]
        while len(children):
            cur = children.pop()
            if isinstance(cur, View):
                setattr(cur, '_ctrl', ctrl)

            children.extend(getattr(cur, 'children', []))
