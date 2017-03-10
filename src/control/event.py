#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Base event handler"
import re

from functools      import wraps
from enum           import Enum, unique
from typing         import (Dict, Union, Sequence, # pylint: disable=unused-import
                            Callable, Tuple, Any, Set, Optional, cast)

from utils          import ismethod, isfunction, toenum

class NoEmission(Exception):
    u"can be raised to stop an emission"
    pass

@unique
class EmitPolicy(Enum):
    u"what elements to add to a fired event"
    outasdict   = 0
    outastuple  = 1
    inputs      = 2
    nothing     = 3
    annotations = 4

class Event:
    u"Event handler class"
    outasdict   = EmitPolicy.outasdict
    outastuple  = EmitPolicy.outastuple
    inputs      = EmitPolicy.inputs
    nothing     = EmitPolicy.nothing
    annotations = EmitPolicy.annotations
    __SIMPLE    = re.compile(r'^(\w|.+)',     re.IGNORECASE)
    __EM_NAME   = re.compile(r'^_?(\w+)',     re.IGNORECASE)
    __OBS_NAME  = re.compile(r'^_?on_?(\w+)', re.IGNORECASE)

    def __init__(self, **kwargs):
        self._handlers = kwargs.get('handlers', dict()) # type: Dict

    @classmethod
    def _emit_list(cls, names, fcn = None) -> 'frozenset':
        u"creates a list of emissions"
        if len(names) == 0 or names[0] is fcn:
            tmp = (cls.__EM_NAME.match(fcn.__name__).group(1),)
            return frozenset(name.lower().strip() for name in tmp)
        else:
            return frozenset(name.lower().strip() for name in names)

    @classmethod
    def _getpolicy(cls, policy, fcn):
        if policy not in (cls.annotations, None):
            return policy

        if policy is cls.annotations:
            if isinstance(fcn, cast(type, staticmethod)):
                fcn = getattr(fcn, '__func__')
            try:
                rta = fcn.__annotations__['return']
            except KeyError as exc:
                raise KeyError("Missing emission policy: "+str(fcn)) from exc
        elif policy is None:
            rta = fcn if fcn is None or isinstance(fcn, type) else type(fcn)

        if rta is None:
            return EmitPolicy.nothing
        elif issubclass(rta, Dict):
            return cls.outasdict
        elif issubclass(rta, (Sequence, Tuple)):
            return cls.outastuple
        else:
            return policy

    @staticmethod
    def _handle_args(lst, policy, ret, args, kwargs):
        if policy in (EmitPolicy.outastuple, EmitPolicy.outasdict):
            return (lst, policy, ret)
        elif policy == EmitPolicy.nothing:
            return (lst, policy)
        else:
            return (lst, policy, (args, kwargs))

    @staticmethod
    def _return(names, fcn):
        u"Applies a wrapVper now or later"
        if len(names) == 1:
            return fcn(names[0])
        else:
            return fcn

    @classmethod
    def _decorate_meth(cls, this, lst, myrt, fcn):
        u"returns a decorator for wrapping methods"
        myrt = cls._getpolicy(myrt, fcn)

        @wraps(fcn)
        def _wrap(clsorself, *args, **kwargs):
            try:
                ret = fcn(clsorself, *args, **kwargs)
            except NoEmission:
                return

            return this.handle(*cls._handle_args(lst, myrt, ret, args, kwargs))
        return _wrap

    @classmethod
    def _decorate_int(cls, lst, myrt, fcn):
        u"returns a decorator for wrapping methods"
        myrt = cls._getpolicy(myrt, fcn)

        @wraps(fcn)
        def _wrap(self, *args, **kwargs):
            try:
                ret = fcn(self, *args, **kwargs)
            except NoEmission:
                return

            return self.handle(*cls._handle_args(lst, myrt, ret, args, kwargs))
        return _wrap

    @classmethod
    def _decorate_func(cls, this, lst, myrt, fcn):
        u"returns a decorator for wrapping free functions"
        myrt = cls._getpolicy(myrt, fcn)

        @wraps(fcn)
        def _wrap(*args, **kwargs):
            try:
                ret = fcn(*args, **kwargs)
            except NoEmission:
                return

            return this.handle(*cls._handle_args(lst, myrt, ret, args, kwargs))
        return _wrap

    def remove(self, name:str, fcn:Callable):
        u"removes an event"
        self._handlers.get(name, set()).discard(fcn)

    def handle(self,
               lst   :'Union[str,Set[str]]',
               policy:'Optional[EmitPolicy]'                 = None,
               args  :'Optional[Union[Tuple,Sequence,Dict]]' = None):
        u"Call handlers only once: collect them all"
        if isinstance(lst, str):
            lst = {lst}

        policy = self._getpolicy(policy, args)

        allfcns = set() # type: Set[Callable]
        for name in lst.intersection(self._handlers):
            allfcns.update(self._handlers[name])

        if   policy is EmitPolicy.outasdict:
            for hdl in allfcns:
                hdl(**cast(Dict, args))
        elif policy is EmitPolicy.outastuple:
            for hdl in allfcns:
                hdl(*args)
        elif policy is EmitPolicy.nothing:
            for hdl in allfcns:
                hdl()
        else:
            for hdl in allfcns:
                hdl(*args[0], **args[1])
        return args

    def emit(self, *names, returns = EmitPolicy.annotations):
        u"wrapped methow will fire events named in arguments"
        def _wrapper(fcn:Callable, myrt = toenum(EmitPolicy, returns)):
            lst = self._emit_list(names, fcn)

            if ismethod(fcn):
                return self._decorate_meth(self, lst, myrt, fcn)
            else:
                return self._decorate_func(self, lst, myrt, fcn)
        return self._return(names, _wrapper)

    @classmethod
    def internalemit(cls, *names, returns = EmitPolicy.annotations):
        u"wrapped methow will fire events named in arguments"
        def _wrapper(fcn:Callable, myrt = returns):
            lst = cls._emit_list(names, fcn)
            return cls._decorate_int(lst, myrt, fcn)

        return cls._return(names, _wrapper)

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
                if self.__SIMPLE.match(name):
                    self._handlers.setdefault(name.lower().strip(), set()).add(fcn)
                else:
                    match = re.compile(name.lower()).match
                    for key in self._handlers:
                        if match(key):
                            self._handlers[key].add(fcn)
            return fcn

        def _fromfcn(fcn:Callable, name = None):
            if name is None:
                name  = fcn.__name__
            match = self.__OBS_NAME.match(name)

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

    def close(self):
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
