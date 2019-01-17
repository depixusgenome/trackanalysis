#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Base event handler"
import re

from itertools          import product
from functools          import wraps, partial
from enum               import Enum, unique
from typing             import (Dict, Union, Sequence, Callable, Tuple, Any, Set,
                                Optional, List, cast)

from utils              import ismethod, isfunction, toenum
from utils.logconfig    import getLogger
LOGS = getLogger(__name__)

class NoEmission(Exception):
    "can be raised to stop an emission"

@unique
class EmitPolicy(Enum):
    "what elements to add to a fired event"
    outasdict   = 0
    outastuple  = 1
    inputs      = 2
    nothing     = 3
    annotations = 4
    @classmethod
    def get(cls, policy:'EmitPolicy', fcn) -> 'EmitPolicy':
        "returns the correct policy"
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

        return (cls.nothing     if rta is None                      else
                cls.outasdict   if issubclass(rta, Dict)            else
                cls.outastuple  if issubclass(rta, (tuple, list))   else
                policy)

    def run(self, allfcns: Set[Callable], args):
        "runs provided observers"
        calllater: List[Callable[[], None]] = []
        if   self is self.outasdict:
            dargs = cast(Dict, args)
            for hdl in allfcns:
                LOGS.debug("observer %s", hdl)
                hdl(**dargs, calllater = calllater)
        elif self is self.outastuple:
            for hdl in allfcns:
                LOGS.debug("observer %s", hdl)
                hdl(*args, calllater = calllater)
        elif self is self.nothing:
            for hdl in allfcns:
                LOGS.debug("observer %s", hdl)
                hdl(calllater = calllater)
        else:
            for hdl in allfcns:
                LOGS.debug("observer %s", hdl)
                hdl(*args[0], **args[1], calllater = calllater)
        for i in calllater:
            LOGS.debug("callater %s", i)
            i()

class EventHandlerContext:
    "handle a list of events repeatedly"
    _fcns:      Callable
    _policy:    EmitPolicy
    def __init__(self, ctrl, lst, policy, args):
        self._ctrl   = ctrl
        self._lst    = lst
        self._args   = policy, args

    def __enter__(self):
        self._fcns   = self._ctrl.getobservers(self._lst)
        self._policy = EmitPolicy.get(cast(EmitPolicy, self._args[0]), self._args[1])
        return self

    def __exit__(self, *_):
        pass

    def handle(self, args):
        "handle events"
        _CNT[0] += 1
        LOGS.debug("[%d] Handling %s (%s)", _CNT[0], self._lst, self._ctrl)
        self._policy.run(self._fcns, args)
        LOGS.debug("[%d] Handled %s (%s)", _CNT[0], self._lst, self._ctrl)

    __call__ = handle

_CNT         = [0]
_COMPLETIONS = Dict[Callable, Set[Callable]]
_HANDLERS    = Dict[str, Union[Set[Callable], _COMPLETIONS]]
class Event:
    "Event handler class"
    emitpolicy  = EmitPolicy
    __SIMPLE    = cast(Callable, re.compile(r'^(\w|\.)+$',   re.IGNORECASE).match)
    __EM_NAME   = re.compile(r'^_*?(\w+)',     re.IGNORECASE).match
    __OBS_NAME  = re.compile(r'^_*?on_*?(\w+)', re.IGNORECASE).match

    def __init__(self, **kwargs):
        self._handlers: _HANDLERS = kwargs.get('handlers', dict())

    def remove(self, *args):
        "removes an event"
        if all(isfunction(i) for i in args):
            for arg in args:
                fcn  = arg.func if isinstance(arg, partial) else arg
                name = self.__OBS_NAME(fcn.__name__).group(1)
                itm  = self._handlers.get(name, None)
                if isinstance(itm, Set):
                    tmp  = {arg, fcn}
                    itm -= {i for i in itm if i in tmp or getattr(i, 'func', None) in tmp}
            return

        name = args[0]
        assert isinstance(name, str)
        itm  = self._handlers.get(name, None)
        if isinstance(itm, Set):
            tmp  = set(args[1:]) | set(i.func if isinstance(i, partial) else i for i in args[1:])
            itm -= {i for i in itm if i in tmp or getattr(i, 'func', None) in tmp}

    def getobservers(self, lst:Union[str,Set[str]]) -> Set[Callable]:
        "returns the list of observers"
        if isinstance(lst, str):
            lst = {lst}

        allfcns = set() # type: Set[Callable]
        for name in lst.intersection(self._handlers):
            allfcns.update(self._handlers[name])

        completions = self._handlers.get('ㄡ', None)
        if completions:
            for fcn, names in cast(_COMPLETIONS, completions).items():
                if any(patt(key) for patt, key in product(names, lst)): # type: ignore
                    allfcns.add(fcn)
        return allfcns

    def handle(self,
               lst   :Union[str,Set[str]],
               policy:Optional[EmitPolicy]                 = None,
               args  :Optional[Union[Tuple,Sequence,Dict]] = None):
        "Call handlers only once: collect them all"
        allfcns = self.getobservers(lst)
        if len(allfcns):
            _CNT[0] += 1
            policy = EmitPolicy.get(cast(EmitPolicy, policy), args)
            LOGS.debug("[%d] Handling %s (%s)", _CNT[0], lst, self)
            policy.run(allfcns, args)
            LOGS.debug("[%d] Handled %s (%s)", _CNT[0], lst, self)
        return args

    def __call__(
            self,
            lst:Union[str,Set[str]],
            policy:Optional[EmitPolicy]                 = None,
            args  :Optional[Union[Tuple,Sequence,Dict]] = None
    ):
        return EventHandlerContext(self, lst, policy, args)

    def emit(self, *names, returns = EmitPolicy.annotations):
        "wrapped methow will fire events named in arguments"
        def _wrapper(fcn:Callable, myrt = toenum(EmitPolicy, returns)):
            lst = self.__emit_list(names, fcn)

            return (self.__decorate_meth(self, lst, myrt, fcn) if ismethod(fcn) else
                    self.__decorate_func(self, lst, myrt, fcn))
        return self.__return(names, _wrapper)

    @classmethod
    def internalemit(cls, *names, returns = EmitPolicy.annotations):
        "wrapped methow will fire events named in arguments"
        def _wrapper(fcn:Callable, myrt = returns):
            lst = cls.__emit_list(names, fcn)
            return cls.__decorate_int(lst, myrt, fcn)

        return cls.__return(names, _wrapper)

    def observe(self, *anames, decorate = None, argstest = None, **kwargs):
        """
        Wrapped method will handle events named in arguments.

        This can be called directly:

        ```python
        event.observe('event 1', 'event 2',  observing_method)
        event.observe(onevent3)
        event.observe({'event1': fcn1, 'event2': fcn2})
        event.observe(event1 = fcn1, event2 = fcn2)
        ```

        or as a wrapper:

        ```python
        @event.observe('event 1', 'event 2')
        def observing_method(*args, **kwargs):
            pass

        @event.observe
        def onevent3(*args, **kwargs):
            pass
        ```
        """
        # Not implemented: could be done by decorating / metaclassing
        # the observer class
        add = lambda x, y: self.__add_func(x, y, decorate = decorate, test = argstest)

        def _fromfcn(fcn:Callable, name = None):
            if name is None:
                name  = (fcn.func if isinstance(fcn, partial) else fcn).__name__
            match = self.__OBS_NAME(name)

            return add((name,), fcn) if match is None else add((match.group(1),), fcn)

        if len(anames) == 1:
            if hasattr(anames[0], 'items'):
                kwargs.update(cast(dict, anames[0]))
                names: Sequence[Any] = tuple()
            elif isinstance(anames[0], (list, tuple)):
                names = anames[0]
            else:
                names = anames
        else:
            names = anames

        if len(kwargs):
            for name, val in kwargs.items():
                _fromfcn(val, name)

        if len(names) == 0:
            return _fromfcn

        if all(isinstance(name, str) for name in names):
            def _wrapper(fcn):
                return add(names, fcn)
            return _wrapper

        if all(isfunction(name) for name in names):
            # dealing with tuples and lists
            for val in names[:-1]:
                _fromfcn(val)
            return _fromfcn(names[-1])

        return add(names[:-1], names[-1])

    class _OneShot:
        def __init__(self, hdls,  name, fcn):
            self._hdls = hdls
            self._name = name
            self._fcn  = fcn

        def __call__(self, *args, **kwa):
            if not len(self.__dict__):
                return None
            assert self in self._hdls[self._name]
            self._hdls[self._name].discard(self)
            fcn = self._fcn
            self.__dict__.clear() # make sure the function cannot be called again
            return fcn(*args, **kwa)

    def oneshot(self, name: str, fcn):
        """
        one shot observation
        """
        name = name.lower().strip()
        shot = self._OneShot(self._handlers, name, fcn)
        self.__add_func([name], shot)
        assert shot in self._handlers[name]

    def close(self):
        "Clear all handlers"
        self._handlers.clear()
        self._handlers = dict()

    @classmethod
    def __emit_list(cls, names, fcn = None) -> frozenset:
        "creates a list of emissions"
        if len(names) == 0 or names[0] is fcn:
            fname = (fcn.func if isinstance(fcn, partial) else fcn).__name__
            tmp   = (getattr(cls.__EM_NAME(fname), 'group')(1),)
            return frozenset(name.lower().strip() for name in tmp)

        return frozenset(name.lower().strip() for name in names)

    @staticmethod
    def __handle_args(lst, policy, ret, args, kwargs):
        if policy in (EmitPolicy.outastuple, EmitPolicy.outasdict):
            return (lst, policy, ret)
        if policy == EmitPolicy.nothing:
            return (lst, policy)
        return (lst, policy, (args, kwargs))

    @staticmethod
    def __return(names, fcn):
        "Applies a wrapVper now or later"
        return fcn(names[0]) if len(names) == 1 else fcn

    @classmethod
    def __decorate_meth(cls, this, lst, myrt, fcn):
        "returns a decorator for wrapping methods"
        myrt = EmitPolicy.get(myrt, fcn)

        @wraps(fcn)
        def _wrap(clsorself, *args, **kwargs):
            try:
                ret = fcn(clsorself, *args, **kwargs)
            except NoEmission:
                return None

            return this.handle(*cls.__handle_args(lst, myrt, ret, args, kwargs))
        return _wrap

    @classmethod
    def __decorate_int(cls, lst, myrt, fcn):
        "returns a decorator for wrapping methods"
        myrt = EmitPolicy.get(myrt, fcn)

        @wraps(fcn)
        def _wrap(self, *args, **kwargs):
            try:
                ret = fcn(self, *args, **kwargs)
            except NoEmission:
                return None

            return self.handle(*cls.__handle_args(lst, myrt, ret, args, kwargs))
        return _wrap

    @classmethod
    def __decorate_func(cls, this, lst, myrt, fcn):
        "returns a decorator for wrapping free functions"
        myrt = EmitPolicy.get(myrt, fcn)

        @wraps(fcn)
        def _wrap(*args, **kwargs):
            try:
                ret = fcn(*args, **kwargs)
            except NoEmission:
                return None

            return this.handle(*cls.__handle_args(lst, myrt, ret, args, kwargs))
        return _wrap

    def __add_func(self, lst, fcn:Callable, decorate = None, test = None):
        if isinstance(fcn, cast(type, staticmethod)):
            fcn = getattr(fcn, '__func__')

        elif ismethod(fcn):
            raise NotImplementedError("observe cannot decorate a "
                                      "method unless it's a static one")

        elif not callable(fcn):
            raise ValueError("observer must be callable")

        if decorate is not None:
            fcn = decorate(fcn)

        if test is not None:
            @wraps(fcn)
            def _fcn(*args, __fcn__ = fcn, __test__ = test, **kwargs):
                return __fcn__(*args, **kwargs) if __test__(*args, **kwargs) else None
            fcn = _fcn

        for name in lst:
            if self.__SIMPLE(name):
                cur = self._handlers.setdefault(name.lower().strip(), set())
                cast(Set, cur).add(fcn)
            else:
                dcur = self._handlers.setdefault('ㄡ', {})
                cast(_COMPLETIONS, dcur).setdefault(fcn, set()).add(re.compile(name).match)

        return fcn

class Controller(Event):
    "Main controller class"
    @classmethod
    def emit(cls, *names, returns = EmitPolicy.annotations):
        "decorator for emitting signals: can only be applied to *Controller* classes"
        return Event.internalemit(*names, returns = returns)

    @staticmethod
    def updatemodel(model, **kwargs) -> dict:
        "updates a model element"
        old = dict()
        for name, val in kwargs.items():
            if getattr(model, name) == val:
                continue

            old[name] = getattr(model, name)
            setattr(model, name, val)

        if len(old) is None:
            raise NoEmission()

        return old
