#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"basic view module"
from functools            import wraps
from typing               import Callable
from bokeh.models.widgets import Button
from bokeh.layouts        import layout

from control     import Controller      # pylint: disable=unused-import
from .keypress   import KeyPressManager # pylint: disable=unused-import

class ActionDescriptor:
    u"""
    For user gui action: surrounds controller action with 2 events.

    This can also be as a descriptor, or a decorator
    """
    def __call__(self, fcn):
        @wraps(fcn)
        def _wrap(this, *args, **kwargs):
            with Action(this._ctrl): # pylint: disable=protected-access
                return fcn(this, *args, **kwargs)
        return _wrap

    def __get__(self, obj, tpe):
        if obj is None:
            # called as a class attribute: to be used as a decorator
            return self
        else:
            # called as an instance attribute:
            # can be used as a context or a decorator
            return Action(obj._ctrl) # pylint: disable=protected-access

class Action(ActionDescriptor):
    u"""
    For user gui action: surrounds controller action with 2 events.

    This can also be as a descriptor, or a decorator
    """
    def __init__(self, ctrl = None):
        self._ctrl = ctrl

    def __enter__(self):
        self._ctrl.handle("startaction")
        return self._ctrl

    def __exit__(self, tpe, val, bkt):
        self._ctrl.handle("stopaction",
                          args = {'type': tpe, 'value': val, 'backtrace': bkt})
        return False

class View:
    u"Classes to be passed a controller"
    action = ActionDescriptor()
    ISAPP  = False
    def __init__(self, **kwargs):
        u"initializes the gui"
        self._ctrl  = kwargs['ctrl']  # type: Controller

    def startup(self, path, script):
        u"runs a script or opens a file on startup"
        with self.action:
            if path is not None:
                self._ctrl.openTrack(path)
            if script is not None:
                script(self, self._ctrl)

    def close(self):
        u"closes the application"
        self._ctrl.close()
        self._ctrl = None

class BokehView(View):
    u"A view with a gui"
    def __init__(self, **kwargs):
        u"initializes the gui"
        super().__init__(**kwargs)
        self._keys = kwargs['keys']  # type: KeyPressManager

    def close(self):
        u"closes the application"
        super().close()
        self._keys.close()
        self._keys = None

    @classmethod
    def open(cls, doc, **kwa):
        u"starts the application"
        self = cls(**kwa)
        self.addtodoc(doc)
        return self

    def addtodoc(self, doc):
        u"Adds one's self to doc"
        doc.add_root(self._keys.getroots()[0])

        roots = self.getroots()
        if len(roots) == 1:
            doc.add_root(roots[0])
        else:
            doc.add_root(layout(roots, sizing_mode = 'stretch_both'))

    def getroots(self):
        u"returns object root"
        raise NotImplementedError("Add items to doc")

    def button(self, fcn:Callable, title:str, prefix = 'keypress', **kwa):
        u"creates and connects a button"
        kwa.setdefault('label', title.capitalize())
        kwa.setdefault('width', self._ctrl.getGlobal('css', 'button.width'))

        btn = Button(**kwa)
        btn.on_click(fcn)
        self._keys.addKeyPress((prefix+'.'+title.lower(), fcn))
        return btn
