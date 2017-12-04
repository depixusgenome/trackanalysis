#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=invalid-name
u"utils for inspecting objects and frames"
import inspect
from   typing    import cast
from   types     import LambdaType, FunctionType, MethodType
from   functools import partial

signature           = inspect.signature
getmembers          = inspect.getmembers
isgeneratorfunction = inspect.isgeneratorfunction

def templateattribute(cls, index) -> type:
    "returns a template attribute"
    cur  = cls
    orig = getattr(cls, '__orig_bases__')
    while orig is None or orig[0].__args__ is None:
        cur  = getattr(cur, '__base__')
        orig = getattr(cur, '__orig_bases__', None)
    return orig[0].__args__[index]    # type: ignore

def isfunction(fcn) -> bool:
    u"Returns whether the object is a function"
    return isinstance(fcn, (LambdaType, FunctionType, MethodType, partial))

def ismethod(fcn) -> bool:
    u"to be called in method decorators"
    if isinstance(fcn, cast(type, classmethod)):
        return True

    elif next(iter(signature(fcn).parameters), '') in ('self', 'cls', 'mcs'):
        return True

    return False

def getlocals(ind) -> dict:
    u"returns the locals from a higher frame"
    return  inspect.stack()[ind+1][0].f_locals
