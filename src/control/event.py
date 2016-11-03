#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Base event handler"
import re

from functools      import wraps
from enum           import Enum, unique
from typing         import Callable, cast

from utils          import ismethod, isfunction, toenum

class NoEmission(Exception):
    u"can be raised to stop an emission"
    pass

@unique
class EmitPolicy(Enum):
    u"what elements to add to a fired event"
    outasdict  = 0
    outastuple = 1
    inputs     = 2
    nothing    = 3

class Event:
    u"Event handler class"
    outasdict  = EmitPolicy.outasdict
    outastuple = EmitPolicy.outastuple
    inputs     = EmitPolicy.inputs
    nothing    = EmitPolicy.nothing

    def __init__(self):
        self._handlers = dict() # type: Dict

    def remove(self, name:str, fcn:Callable):
        u"removes an event"
        self._handlers.get(name, set()).discard(fcn)

    def callhandlers(self, lst, policy, ret):
        u"Call handlers only once: collect them all"
        allfcns = set()
        for name in lst.intersection(self._handlers):
            allfcns.update(self._handlers[name])

        if   policy is EmitPolicy.outasdict:
            for hdl in allfcns:
                hdl(**ret[0])
        elif policy is EmitPolicy.outastuple:
            for hdl in allfcns:
                hdl(*ret[0])
        elif policy is EmitPolicy.nothing:
            for hdl in allfcns:
                hdl()
        else:
            for hdl in allfcns:
                hdl(*ret[1], **ret[2])
        return ret

    _EM_NAME = re.compile(r'^_?(\w+)', re.IGNORECASE)
    @classmethod
    def _emissionList(cls, names, fcn = None) -> 'frozenset':
        u"creates a list of emissions"
        if len(names) == 0 or names[0] is fcn:
            tmp = (cls._EM_NAME.match(fcn.__name__).group(1),)
            return frozenset(name.lower().strip() for name in tmp)
        else:
            return frozenset(name.lower().strip() for name in names)

    @classmethod
    def _wrapEmittingMethod(cls, this, lst, myrt, fcn):
        u"returns a decorator for wrapping methods"
        @wraps(fcn)
        def _wrap(clsorself, *args, **kwargs):
            try:
                ret = fcn(clsorself, *args, **kwargs)
            except NoEmission:
                return

            return this.callhandlers(lst, myrt, (ret, args, kwargs))
        return _wrap

    @classmethod
    def _wrapEmittingInternal(cls, lst, myrt, fcn):
        u"returns a decorator for wrapping methods"
        @wraps(fcn)
        def _wrap(self, *args, **kwargs):
            try:
                ret = fcn(self, *args, **kwargs)
            except NoEmission:
                return

            return self.callhandlers(lst, myrt, (ret, args, kwargs))
        return _wrap

    @classmethod
    def _wrapEmittingFunction(cls, this, lst, myrt, fcn):
        u"returns a decorator for wrapping free functions"
        @wraps(fcn)
        def _wrap(*args, **kwargs):
            try:
                ret = fcn(*args, **kwargs)
            except NoEmission:
                return

            return this.callhandlers(lst, myrt, (ret, args, kwargs))
        return _wrap

    @staticmethod
    def _returnWrapper(names, fcn):
        u"Applies a wrapper now or later"
        if len(names) == 1:
            return fcn(names[0])
        else:
            return fcn

    def emit(self, *names, returns = EmitPolicy.inputs):
        u"wrapped methow will fire events named in arguments"
        def _wrapper(fcn:Callable, myrt = toenum(EmitPolicy, returns)):
            lst = self._emissionList(names, fcn)

            if ismethod(fcn):
                return self._wrapEmittingMethod(self, lst, myrt, fcn)
            else:
                return self._wrapEmittingFunction(self, lst, myrt, fcn)
        return self._returnWrapper(names, _wrapper)

    @classmethod
    def internalemit(cls, *names, returns = EmitPolicy.inputs):
        u"wrapped methow will fire events named in arguments"
        def _wrapper(fcn:Callable, myrt = returns):
            lst = cls._emissionList(names, fcn)
            return cls._wrapEmittingInternal(lst, myrt, fcn)

        return cls._returnWrapper(names, _wrapper)

    _OBS_NAME = re.compile(r'^_?on_?(\w+)', re.IGNORECASE)
    def observe(self, *names, **kwargs):
        u"""
        Wrapped method will handle events named in arguments.

        This can be called directly:

        > event.observe('event 1', 'event 2',  observing_method)
        > event.observe(onevent3)
        > event.observe({'event1': fcn1, 'event2': fcn2})
        > event.observe(event1 = fcn1, event2 = fcn2)

        or as a wrapper:

        > @event.observe('event 1', 'event 2')
        > def observing_method(*args, **kwargs): pass

        > @event.observe
        > def onevent3(*args, **kwargs): pass
        """
        # Not implemented: could be done by decorating / metaclassing
        # the observer class
        def _add(lst, fcn:Callable):
            if isinstance(fcn, cast(type, staticmethod)):
                fcn = getattr(fcn, '__func__')

            elif ismethod(fcn):
                raise NotImplementedError("observe cannot decorate a "
                                          "method unless it's a static one")

            elif not callable(fcn):
                raise ValueError("observer must be callable")

            for name in lst:
                self._handlers.setdefault(name.lower().strip(), set()).add(fcn)
            return fcn

        def _fromfcn(fcn:Callable, name = None):
            if name is None:
                name  = fcn.__name__
            match = self._OBS_NAME.match(name)

            if match is None:
                return _add((name,), fcn)
            else:
                return _add((match.group(1),), fcn)

        if len(names) == 1:
            if hasattr(names[0], 'items'):
                kwargs.update(names[0])
                names = tuple()
            elif isinstance(names[0], (list, tuple)):
                names = names[0]

        if len(kwargs):
            for name, val in kwargs.items():
                _fromfcn(val, name)

        if len(names) == 0:
            return _fromfcn

        if all(isinstance(name, str) for name in names):
            def _wrapper(fcn):
                return _add(names, fcn)
            return _wrapper

        if all(isfunction(name) for name in names):
            # dealing with tuples and lists
            for val in names:
                _fromfcn(val)
            return

        return _add(names[:-1], names[-1])

    def unobserve(self):
        u"Clear all handlers"
        self._handlers.clear()
        self._handlers = dict()

class Controller(Event):
    u"Main controller class"
    @classmethod
    def emit(cls, *args, **kwargs):
        u"decorator for emitting signals: can only be applied to *Controller* classes"
        return Event.internalemit(*args, **kwargs)

    @staticmethod
    def updateModel(model, **kwargs) -> dict:
        u"updates a model element"
        old = dict()
        for name, val in kwargs.items():
            if getattr(model, name) == val:
                continue

            old[name] = getattr(model, name)
            setattr(model, name, val)

        if len(old) is None:
            raise NoEmission()

        return old
