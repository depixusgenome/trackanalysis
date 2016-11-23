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

def _iterate(item, fcn, *args):
    curr = getattr(item.__class__, fcn)
    for base in item.__class__.__bases__:
        other = getattr(base, fcn, curr)
        if other is not curr and other not in (observe, unobserve):
            other(item, *args)

    children = list(getattr(item, 'children', []))
    while len(children):
        cur = children.pop()
        if isinstance(cur, (View, FlexxView)):
            getattr(cur, fcn)(*args)
        else:
            children.extend(getattr(cur, 'children', []))

def unobserve(item):
    u"Removes the controller"
    if '_ctrl' in item.__dict__:
        getattr(item, '_ctrl').unobserve()
        item.__dict__.pop('_ctrl')

    if 'keys' in item.__dict__:
        item.keys.popKeyPress(all)
        del item.keys
    _iterate(item, 'unobserve')

def observe(item, ctrl:Controller, keys:KeyPressManager):
    u"Sets up the controller"
    if '_ctrl' not in item.__dict__:
        setattr(item, '_ctrl', ctrl)

    if 'keys' not in item.__dict__:
        item.keys = keys

    _iterate(item, 'observe', ctrl, keys)

def startup(item, path, script):
    u"runs a script or opens a file on startup"
    with item.action:
        if path is not None:
            getattr(item, '_ctrl').openTrack(path)
        if script is not None:
            script(item, getattr(item, '_ctrl'))


class View:
    u"Classes to be passed a controller"
    _ctrl     = None    # type: Controller
    keys      = None    # type: KeyPressManager
    action    = ActionDescriptor()
    observe   = observe
    unobserve = unobserve
    startup   = startup

class FlexxView(ui.Widget):
    u"A view with a gui"
    _ctrl     = None    # type: Controller
    keys      = None    # type: KeyPressManager
    action    = ActionDescriptor()
    observe   = observe
    unobserve = unobserve
    startup   = startup

    def init(self):
        u"initializes the gui"
        raise NotImplementedError("Use this to create the gui")

    def open(self, ctrl):
        u"starts up the controller stuff"
        keys = KeyPressManager()
        keys.observe(ctrl, 'keypress', quit = self.close)
        self.connect("key_press", keys.onKeyPress)
        self.observe(ctrl, keys)

    def close(self):
        u"closes the application"
        self.keys.unobserve()
        self.unobserve()
        self.session.close()

    def button(self, fcn:Callable, title:str, prefix = 'keypress', **kwa):
        u"creates and connects a button"
        if 'text' not in kwa:
            kwa['text'] = u'<u>{}</u>{}'.format(title[0].upper(), title[1:])

        btn = ui.Button(**kwa)
        btn.connect('mouse_down', fcn)
        self.keys.addKeyPress((prefix+'.'+title.lower(), fcn))
