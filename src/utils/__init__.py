#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"utils"
from typing         import Callable, cast
from types          import LambdaType, FunctionType, MethodType
from enum           import Enum
from contextlib     import contextmanager
from inspect        import signature, ismethod as _ismeth, isfunction as _isfunc, getmembers
from functools      import wraps
import re

def toenum(tpe, val):
    u"returns an enum object"
    if isinstance(val, str):
        return tpe.__members__[val]
    elif isinstance(val, int):
        return tpe(val)
    elif isinstance(val, tpe):
        return val
    elif val is not None:
        raise TypeError('"level" attribute has incorrect type')

def isfunction(fcn) -> bool:
    u"Returns whether the object is a function"
    return isinstance(fcn, (LambdaType, FunctionType, MethodType))

def ismethod(fcn) -> bool:
    u"to be called in method decorators"
    if isinstance(fcn, cast(type, classmethod)):
        return True

    elif next(iter(signature(fcn).parameters), '') in ('self', 'cls', 'mcs'):
        return True

    return False

class MetaMixin(type):
    u"""
    Mixes base classes together.

    Mixin classes are actually composed. That way there are fewer name conflicts
    """
    def __new__(mcs, name, bases, nspace, **kw):
        match  = re.compile(kw.get('match', r'^[a-z][a-zA-Z0-9]+$')).match
        mixins = kw['mixins']
        shared = kw.get('shared', tuple())

        def setMixins(self, items = tuple(), shared = tuple()):
            u"sets-up composed mixins"
            for base in mixins:
                name =  base.__name__.lower()
                if name in items:
                    setattr(self, name, items[name])
                elif getattr(self, name, None) is None:
                    setattr(self, name, base())

            for name in shared:
                attr = getattr(self.getMixin(mixins[0]), name)
                for base in mixins[1:]:
                    setattr(self.getMixin(base), name, attr)

        nspace['setMixins'] = setMixins

        def getMixin(self, base):
            u"returns the mixin associated with a class"
            return getattr(self, base.__name__.lower(), None)

        nspace['getMixin'] = getMixin

        def __init__(self, *args, **kwa):
            for base in bases:
                base.__init__(self, *args, **kwa)
            self.setMixins(mixins, shared)

        nspace['__init__'] = __init__

        for base in mixins:
            for name, fcn in getmembers(base):
                if match(name) is None:
                    continue

                if _ismeth(fcn) or (_isfunc(fcn) and not ismethod(fcn)):
                    nspace[name] = mcs.__createstatic(fcn)
                elif _isfunc(fcn):
                    nspace[name] = mcs.__createmethod(base, fcn)
                elif isinstance(fcn, Enum):
                    nspace[name] = fcn
                elif isinstance(fcn, property):
                    nspace[name] = mcs.__createprop(base, fcn)

        return type(name, bases, nspace)

    @staticmethod
    def __createstatic(fcn):
        @wraps(fcn)
        def _wrap(*args, **kwa):
            return fcn(*args, **kwa)
        return staticmethod(_wrap)

    @staticmethod
    def __createmethod(base, fcn):
        cname = base.__name__.lower()
        @wraps(fcn)
        def _wrap(self, *args, **kwa):
            return fcn(getattr(self, cname), *args, **kwa)
        return _wrap

    @staticmethod
    def __createprop(base, prop):
        fget = (None if prop.fget is None
                else lambda self: prop.fget(self.getMixin(base)))
        fset = (None if prop.fset is None
                else lambda self, val: prop.fset(self.getMixin(base), val))
        fdel = (None if prop.fdel is None
                else lambda self: prop.fdel(self.getMixin(base)))

        return property(fget, fset, fdel, prop.__doc__)
