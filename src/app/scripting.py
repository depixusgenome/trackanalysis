#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Means for using the app as an API"
from tornado.ioloop     import IOLoop
from bokeh.model        import Model

import bokeh.core.properties as props

from utils.logconfig    import getLogger
from control.action     import Action
LOGS = getLogger(__name__)

class Orders(list):
    "A list of orders to apply to the app"
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

INITIAL_ORDERS = Orders()

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

class DpxLoaded(Model):
    """
    This starts tests once flexx/browser window has finished loading
    """
    __implementation__ = """
        import *        as $    from "jquery"
        import *        as p    from "core/properties"
        import {Model}          from "model"
        import {BokehView} from "core/bokeh_view"

        export class DpxLoadedView extends BokehView

        export class DpxLoaded extends Model
            default_view: DpxLoadedView
            type: "DpxLoaded"
            constructor : (attributes, options) ->
                super(attributes, options)
                $((e) => @done = 1)
            @define {
                done:  [p.Number, 0]
            }
                         """
    done = props.Int(0)
