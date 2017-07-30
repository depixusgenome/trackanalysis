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

    def __script(self, view, doc = None):
        "creates a function for running the orders"
        ctrl    = getattr(view, '_ctrl', view)
        nextfcn = getattr(doc, 'add_next_tick_callback', lambda i: i())
        lst     = list(self)
        def _cmd():
            if len(lst):
                with Action(ctrl):
                    lst.pop(0)(ctrl)
                nextfcn(_cmd)
        return _cmd

    def run(self, viewcls, doc = None, onload = None):
        "runs a script"
        if doc is None:
            doc = DummyDoc()

        view   = viewcls.open(doc)
        script = self.__script(view, doc)
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
        return view

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
    orders().dyn_loads.extend(names)

class DummyDoc:
    "dummy document used for scripting"
    def __init__(self):
        self.roots = []
        self.title = ''

    def add_root(self, i):
        "adds a root"
        self.roots.append(i)

    @staticmethod
    def add_next_tick_callback(fcn):
        "runs a command"
        fcn()

if 'scripting' not in sys.modules:
    class DpxLoaded(Model):
        "This starts tests once flexx/browser window has finished loading"
        __implementation__ = "scripting.coffee"
        done = props.Int(0)
