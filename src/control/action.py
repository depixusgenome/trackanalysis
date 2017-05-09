#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"allows fencing multiple events between 2 *startaction* and *stopaction* events"

from typing             import Callable, Optional, Tuple # pylint: disable=unused-import
from functools          import wraps
from inspect            import signature

from utils.logconfig    import getLogger, logging
LOGS = getLogger(__name__)

class _Calls:
    "Dummy class which delays calls to _m_defaults"
    def __init__(self, calls):
        self._calls = calls

    def __str__(self):
        if self._calls is None:
            self._calls = "!?!"

        elif isinstance(self._calls, tuple):
            self._calls = "%s@%s [%s]" % self._calls

        elif hasattr(self._calls, '__code__'):
            fcn  = self._calls # type: ignore
            code = getattr(fcn, '__code__')
            if code is not None:
                self._calls = "%s@%s [%s]" % (getattr(code, 'co_filename', '?'),
                                              getattr(code, 'co_firstlineno', '?'),
                                              getattr(fcn, '__qualname__', ''))
            else:
                self._calls = getattr(fcn, '__qualname__', '')

        return self._calls

class Action:
    """
    For user gui action: surrounds controller action with 2 events.

    This can also be as a descriptor, or a decorator
    """
    _CNT      = [0]
    _STARTEVT = 'startaction'
    _STOPEVT  = 'stopaction'

    def __init__(self, ctrl = None, calls = None, test = None) -> None:
        self._ctrl  = getattr(ctrl, '_ctrl', ctrl)
        assert hasattr(self._ctrl, 'handle')
        self._test  = test
        if calls is not None:
            self._calls = _Calls(calls)
        elif LOGS.getEffectiveLevel() == logging.DEBUG:
            self._calls = _Calls(LOGS.findCaller()[:3])
        else:
            self._calls = _Calls(None)

    def _logstart(self):
        if self._CNT == 1:
            LOGS.debug("current action is %s", self._calls)

    def _logstop(self, val, errvalue):
        if self._CNT[0] == 0 and val is None:
            LOGS.debug("done action %s", self._calls)

        elif val is not None:
            if errvalue[0] and (len(val.args) != 2 or val.args[1] != 'warning'):
                LOGS.error("failed action %s", self._calls)
                LOGS.exception(val)
            else:
                LOGS.debug("failed action %s", self._calls)

    def __enter__(self):
        self._CNT[0] += 1
        self._ctrl.handle(self._STARTEVT, args = {'recursive': self._CNT[0] > 1})
        self._logstart()
        return self._ctrl

    def __call__(self, fcn: Callable, calls = None, test = None):
        if test is None:
            test = self._test

        action = type(self)(self, calls = fcn)
        if tuple(signature(fcn).parameters) == ('attr', 'old', 'new'):
            # Special Bokeh callback context
            @wraps(fcn)
            def _wrap_cb(attr, old, new):
                if test is None or test(new):
                    with action:
                        fcn(attr, old, new)
            return _wrap_cb
        elif tuple(signature(fcn).parameters)[1:] == ('attr', 'old', 'new'):
            # Special Bokeh callback context
            @wraps(fcn)
            def _wraps_cb(self, attr, old, new):
                if test is None or test(new):
                    with action:
                        fcn(self, attr, old, new)
            return _wraps_cb
        else:
            @wraps(fcn)
            def _wrap_normal(*args, **kwargs):
                if test is None or test(*args, **kwargs):
                    with action:
                        return fcn(*args, **kwargs)
            return _wrap_normal

    def __exit__(self, tpe, val, bkt):
        self._CNT[0] -= 1
        errvalue = [self._ctrl.getGlobal('config').catcherror.get()]
        self._ctrl.handle(self._STOPEVT,
                          args = {'type':       tpe,
                                  'value':      val,
                                  'catcherror': errvalue,
                                  'backtrace':  bkt,
                                  'recursive':  self._CNT[0] > 0})
        self._logstop(val, errvalue)
        return errvalue[0]

class Computation(Action):
    "threaded action which must *not* update the model"
    _CNT      = [0]
    _STARTEVT = 'startcomputation'
    _STOPEVT  = 'stopcomputation'

class ActionDescriptor:
    """
    For user gui action: surrounds controller action with 2 events.

    This can also be as a descriptor, or a decorator
    """
    def __init__(self, action, test = None):
        self.type = action
        self.test = test

    def __call__(self, fcn, calls = None):
        if calls is None:
            calls = _Calls(fcn)

        if tuple(signature(fcn).parameters)[1:] == ('attr', 'old', 'new'):
            @wraps(fcn)
            def _wrap_cb(this, attr, old, new):
                if self.test is None or self.test(new):
                    with self.type(this, calls = calls):
                        fcn(this, attr, old, new)
            return _wrap_cb
        else:
            @wraps(fcn)
            def _wrap_cb(this, *args, **kwa):
                if self.test is None or self.test(*args, **kwa):
                    with self.type(this, calls = calls):
                        fcn(this, *args, **kwa)
            return _wrap_cb

    def __get__(self, obj, tpe):
        if obj is None:
            # called as a class attribute: to be used as a decorator
            return self

        calls = None # type: Optional[Tuple]
        if LOGS.getEffectiveLevel() == logging.DEBUG:
            # called as an instance attribute:
            # can be used as a context or a decorator
            calls = LOGS.findCaller()[:3]
        return self.type(obj, calls = calls, test = self.test)
