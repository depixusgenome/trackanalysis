#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"allows fencing multiple events between 2 *startaction* and *stopaction* events"

from typing             import Callable
from functools          import wraps
from inspect            import signature

from utils.logconfig    import getLogger
LOGS = getLogger(__name__)

class ActionDescriptor:
    """
    For user gui action: surrounds controller action with 2 events.

    This can also be as a descriptor, or a decorator
    """
    def __call__(self, fcn, calls = None):
        if calls is None:
            calls = self.defaults(fcn)

        @wraps(fcn)
        def _wrap(this, *args, **kwargs):
            with Action(this, calls = calls):
                return fcn(this, *args, **kwargs)
        return _wrap

    @staticmethod
    def defaults(fcn):
        "returns default values for calls"
        return (fcn.__code__.co_filename,
                fcn.__code__.co_firstlineno,
                fcn.__qualname__)

    def __get__(self, obj, tpe):
        if obj is None:
            # called as a class attribute: to be used as a decorator
            return self
        else:
            # called as an instance attribute:
            # can be used as a context or a decorator
            return Action(obj, calls = LOGS.findCaller()[:3])

_CNT = [0]
class Action(ActionDescriptor):
    """
    For user gui action: surrounds controller action with 2 events.

    This can also be as a descriptor, or a decorator
    """
    def __init__(self, ctrl = None, calls = None) -> None:
        self._ctrl  = getattr(ctrl, '_ctrl', ctrl)
        if calls is None:
            self._calls = LOGS.findCaller()[:3]
        else:
            self._calls = calls

    def __enter__(self):
        _CNT[0] += 1
        self._ctrl.handle("startaction", args = {'recursive': _CNT[0] > 1})
        if _CNT == 1:
            LOGS.debug("current action is %s@%s [%s]", *self._calls)
        return self._ctrl

    def __call__(self, fcn: Callable, calls = None):
        if calls is None:
            defaults = self.defaults(fcn)

        action = Action(self, calls = defaults)
        if tuple(signature(fcn).parameters) == ('attr', 'old', 'new'):
            # Special Bokeh callback context
            @wraps(fcn)
            def _wrap_cb(attr, old, new):
                with action:
                    fcn(attr, old, new)
            return _wrap_cb
        elif tuple(signature(fcn).parameters)[1:] == ('attr', 'old', 'new'):
            # Special Bokeh callback context
            @wraps(fcn)
            def _wraps_cb(self, attr, old, new):
                with action:
                    fcn(self, attr, old, new)
            return _wraps_cb
        else:
            return super().__call__(fcn, calls = calls)

    def __exit__(self, tpe, val, bkt):
        _CNT[0] -= 1
        errvalue = [self._ctrl.getGlobal('config').catcherror.get()]
        self._ctrl.handle("stopaction",
                          args = {'type':       tpe,
                                  'value':      val,
                                  'catcherror': errvalue,
                                  'backtrace':  bkt,
                                  'recursive':  _CNT[0] > 0})

        if _CNT == 0 and val is None:
            LOGS.debug("done action %s@%s [%s]", *self._calls)
        elif val is not None:
            if errvalue[0] and (len(val.args) != 2 or val.args[1] != 'treated'):
                LOGS.error("failed action %s@%s [%s]", *self._calls)
                LOGS.exception(val)
            else:
                LOGS.debug("failed action %s@%s [%s]", *self._calls)
        return errvalue[0]
