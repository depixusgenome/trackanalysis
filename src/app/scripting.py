#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Means for using the app as an API"
from typing             import List, Callable
import sys
from tornado.ioloop     import IOLoop
from bokeh.model        import Model

import bokeh.core.properties as props

from utils.logconfig    import getLogger
from control.action     import Action
LOGS = getLogger(__name__)

class Orders(list):
    "A list of orders to apply to the app"
    def __init__(self):
        super().__init__()
        self.default_config: Callable  = lambda x: None
        self.dyn_loads:      List[str] = []

    def __script(self, ctrl, doc = None):
        "creates a function for running the orders"
        nextfcn = getattr(doc, 'add_next_tick_callback', lambda i: i())
        lst     = ['guiloaded'] + list(self) + ["scriptsdone"]

        def _cmd():
            if len(lst) == 0:
                return

            cmd = lst.pop(0)
            if callable(cmd):
                with Action(ctrl):
                    cmd(ctrl)
            else:
                ctrl.display.handle(cmd, ctrl.display.emitpolicy.nothing)
            nextfcn(_cmd)
        return _cmd

    def run(self, viewcls, doc = None, onload = None):
        "runs a script"
        if doc is None:
            doc = DummyDoc()

        ctrl   = viewcls.open(doc)
        script = self.__script(ctrl, doc)
        if isinstance(doc, DummyDoc):
            if onload is not None:
                onload()

            loop = IOLoop.current()
            loop.run_sync(script)
        else:
            loaded = DpxLoaded()
            doc.add_root(loaded)
            if onload is not None:
                loaded.on_change('done', lambda attr, old, new: (onload(), script()))
            else:
                loaded.on_change('done', lambda attr, old, new: script())
        return ctrl

    def dynloads(self):
        "returns dynamic loads"
        return self.dyn_loads

    def config(self, arg):
        "returns default config"
        return self.default_config(arg)

INITIAL_ORDERS = Orders()
def orders():
    "returns default orders"
    return INITIAL_ORDERS

def addload(*names):
    "adds a dyn load to the inital orders"
    loads = orders().dyn_loads
    loads.extend([i for i in names if i not in loads])

class DummyDoc:
    "dummy document used for scripting"
    def __init__(self):
        self.roots: list = []
        self.title = ''

    def add_root(self, i):
        "adds a root"
        self.roots.append(i)

    @staticmethod
    def add_next_tick_callback(fcn):
        "runs a command"
        fcn()

if 'scripting' not in sys.modules:
    from view.static import ROUTE

    class DpxLoaded(Model):
        "This starts tests once browser window has finished loading"
        __implementation__ = "scripting.coffee"
        __javascript__     = ROUTE+"/jquery.min.js"
        done       = props.Int(0)
        resizedfig = props.Instance(Model)
