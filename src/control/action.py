#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"allows fencing multiple events between 2 *startaction* and *stopaction* events"

from typing      import Callable
from functools   import wraps
from inspect     import signature

class ActionDescriptor:
    """
    For user gui action: surrounds controller action with 2 events.

    This can also be as a descriptor, or a decorator
    """
    def __call__(self, fcn):
        @wraps(fcn)
        def _wrap(this, *args, **kwargs):
            with Action(this):
                return fcn(this, *args, **kwargs)
        return _wrap

    def __get__(self, obj, tpe):
        if obj is None:
            # called as a class attribute: to be used as a decorator
            return self
        else:
            # called as an instance attribute:
            # can be used as a context or a decorator
            return Action(obj)

_CNT = [0]
class Action(ActionDescriptor):
    """
    For user gui action: surrounds controller action with 2 events.

    This can also be as a descriptor, or a decorator
    """
    def __init__(self, ctrl = None) -> None:
        self._ctrl = getattr(ctrl, '_ctrl', ctrl)

    def __enter__(self):
        _CNT[0] += 1
        self._ctrl.handle("startaction", args = {'recursive': _CNT[0] > 1})
        return self._ctrl

    def __call__(self, fcn: Callable):
        if tuple(signature(fcn).parameters) == ('attr', 'old', 'new'):
            # Special Bokeh callback context
            @wraps(fcn)
            def _wrap_cb(attr, old, new):
                with self:
                    fcn(attr, old, new)
            return _wrap_cb
        elif tuple(signature(fcn).parameters)[1:] == ('attr', 'old', 'new'):
            # Special Bokeh callback context
            @wraps(fcn)
            def _wraps_cb(self, attr, old, new):
                with self:
                    fcn(self, attr, old, new)
            return _wraps_cb
        else:
            return super().__call__(fcn)

    def __exit__(self, tpe, val, bkt):
        _CNT[0] -= 1
        errvalue = [False]
        self._ctrl.handle("stopaction",
                          args = {'type':       tpe,
                                  'value':      val,
                                  'catcherror': errvalue,
                                  'backtrace':  bkt,
                                  'recursive':  _CNT[0] > 0})
        return errvalue[0]
