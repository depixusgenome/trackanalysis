#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"basic view module"
from typing         import Optional     # pylint: disable=unused-import
from control.event  import Controler    # pylint: disable=unused-import

class View:
    u"Classes to be passed a controler"
    MainControl = type(None)
    def mainInit(self):
        u"creates the views and the session specific controler"
        super().init()
        ctrl = self.__class__.MainControl() # py
        if ctrl is None:
            return

        setattr(self, '_ctrl', ctrl)
        children = [self]
        while len(children):
            cur = children.pop()
            if isinstance(cur, View):
                setattr(cur, '_ctrl', ctrl)

            children.extend(getattr(cur, 'children', []))
