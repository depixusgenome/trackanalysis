#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"basic view module"
from typing         import Callable
from functools      import wraps

from flexx          import ui

from control        import Controller
from .keypress      import KeyPressManager

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

class BaseView:
    u"View interface"
    def observe(self, ctrl:Controller):
        u"Sets up the controller"
        raise NotImplementedError()

    def unobserve(self):
        u"removes up the controller"
        raise NotImplementedError()

class View(BaseView):
    u"Classes to be passed a controller"
    _ctrl = None    # type: Controller
    _keys = KeyPressManager()
    def unobserve(self):
        u"Removes the controller"
        if '_ctrl' in self.__dict__:
            self._ctrl.unobserve()
            del self._ctrl

        if '_keys' in self.__dict__:
            self._keys.popKeyPress(all)
            del self._keys

        children = list(getattr(self, 'children', []))
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
            self._ctrl   = ctrl

        children = list(getattr(self, 'children', []))
        while len(children):
            cur = children.pop()
            if isinstance(cur, View):
                cur.observe(ctrl)
            else:
                children.extend(getattr(cur, 'children', []))

    def startup(self, path, script):
        u"runs a script or opens a file on startup"
        if path is not None:
            self._ctrl.openTrack(path)
        if script is not None:
            script(self, self._ctrl)

    action = ActionDescriptor()

class FlexxView(ui.Widget, View):
    u"A view with a gui"
    def init(self):
        u"initializes the gui"
        raise NotImplementedError("Use this to create the gui")

    def open(self, ctrl):
        u"starts up the controller stuff"
        View._keys.observe(ctrl, 'keypress', quit = self.close)
        self.connect("key_press", View._keys.onKeyPress)
        self.observe(ctrl)

    def close(self):
        u"closes the application"
        View._keys.unobserve()
        self.unobserve()
        self.session.close()

    def button(self, fcn:Callable, title:str, prefix = 'keypress', **kwa):
        u"creates and connects a button"
        if 'text' not in kwa:
            kwa['text'] = u'<u>{}</u>{}'.format(title[0].upper(), title[1:])

        btn = ui.Button(**kwa)
        btn.connect('mouse_down', fcn)
        self._keys.addKeyPress((prefix+'.'+title.lower(), fcn))
