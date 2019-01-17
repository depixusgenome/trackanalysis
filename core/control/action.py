#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"allows fencing multiple events between 2 *startaction* and *stopaction* events"

from typing             import Callable, Union, Optional, Tuple
from pathlib            import Path
from functools          import wraps
from inspect            import signature
from time               import time

from utils.logconfig    import getLogger, logging
LOGS = getLogger(__name__)

class _Calls:
    "Dummy class which delays calls to _m_defaults"
    def __init__(self, calls):
        self._calls = calls
        self._start  = None

    def __str__(self):
        if self._calls is None:
            self._calls = "!?!"

        elif isinstance(self._calls, tuple):
            path  = Path(self._calls[0])
            fname = str(path.relative_to(path.parent.parent))
            self._calls = f"{fname}@{self._calls[1]} [{self._calls[2]}]"

        elif hasattr(self._calls, '__code__'):
            fcn  = self._calls # type: ignore
            code = getattr(fcn, '__code__')
            if code is not None:
                fname = '?'
                if hasattr(code, 'co_filename'):
                    path  = Path(code.co_filename)
                    fname = str(path.relative_to(path.parent.parent))

                self._calls = "%s@%s [%s]" % (fname,
                                              getattr(code, 'co_firstlineno', '?'),
                                              getattr(fcn, '__qualname__', ''))
            else:
                self._calls = getattr(fcn, '__qualname__', '')

        elif self._start is not None:
            return self._calls + ' T%.3f' % (time() - self._start)

        self._start = time()
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
        ctrl        = getattr(ctrl, '_ctrl', ctrl)
        ctrl        = getattr(ctrl, 'display', ctrl)
        self._ctrl  = ctrl
        assert hasattr(ctrl, 'handle'), f"{ctrl} has not handle method"
        self._test  = test
        if calls is not None:
            self._calls = _Calls(calls)
        elif LOGS.getEffectiveLevel() == logging.DEBUG:
            self._calls = _Calls(LOGS.findCaller()[:3])
        else:
            self._calls = _Calls(None)

    @property
    def type(self):
        "return the action type"
        return type(self)

    def _logstart(self):
        if self._CNT[0] == 1:
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
        self._logstart()
        self._ctrl.handle(self._STARTEVT, args = {'recursive': self._CNT[0] > 1})
        return self._ctrl

    def withcalls(self, calls) -> 'Action':
        "sets calls"
        self._calls = _Calls(calls)
        return self

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

        if tuple(signature(fcn).parameters)[1:] == ('attr', 'old', 'new'):
            # Special Bokeh callback context
            @wraps(fcn)
            def _wraps_cb(self, attr, old, new):
                if test is None or test(new):
                    with action:
                        fcn(self, attr, old, new)
            return _wraps_cb

        @wraps(fcn)
        def _wrap_normal(*args, **kwargs):
            if test is None or test(*args, **kwargs):
                with action:
                    return fcn(*args, **kwargs)
            return None
        return _wrap_normal

    def __exit__(self, tpe, val, bkt):
        assert val is None or isinstance(val, Exception), f"{val} should be None or Exception"
        self._CNT[0] -= 1
        errvalue      = [getattr(self._ctrl, 'CATCHERROR', True)]

        try:
            self._ctrl.handle(self._STOPEVT,
                              args = {'type':       tpe,
                                      'value':      val,
                                      'catcherror': errvalue,
                                      'backtrace':  bkt,
                                      'recursive':  self._CNT[0] > 0})
            self._logstop(val, errvalue)
        except Exception as exc: # pylint: disable=broad-except
            LOGS.exception(exc)
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
    def __init__(self, action: Union[str, type] = Action, test = None) -> None:
        assert action in ('action', 'computation', Action, Computation)
        self.type = Action if action in (Action, 'action') else Computation
        self.test = test

    def __set_name__(self, _, name):
        assert name in ('action', 'computation')
        self.type = Action if name == 'action' else Computation

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

        @wraps(fcn)
        def _wrap_cb2(this, *args, **kwa):
            if self.test is None or self.test(*args, **kwa):
                with self.type(this, calls = calls):
                    fcn(this, *args, **kwa)
        return _wrap_cb2

    def __get__(self, obj, tpe):
        if obj is None:
            # called as a class attribute: to be used as a decorator
            return self

        calls: Optional[Tuple] = None
        if LOGS.getEffectiveLevel() == logging.DEBUG:
            # called as an instance attribute:
            # can be used as a context or a decorator
            calls = LOGS.findCaller()[:3]
        return self.type(obj, calls = calls, test = self.test)
