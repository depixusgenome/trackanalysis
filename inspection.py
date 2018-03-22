#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=invalid-name
"utils for inspecting objects and frames"
import inspect
from   typing    import Optional, cast
from   types     import LambdaType, FunctionType, MethodType
from   functools import partial

signature           = inspect.signature
getmembers          = inspect.getmembers
isgeneratorfunction = inspect.isgeneratorfunction

def templateattribute(cls, index) -> type:
    "returns a template attribute"
    if not isinstance(cls, type):
        cls = type(cls)
    cur  = cls
    orig = getattr(cls, '__orig_bases__')
    while orig is None or orig[0].__args__ is None:
        cur  = getattr(cur, '__base__')
        orig = getattr(cur, '__orig_bases__', None)
    return orig[0].__args__[index]    # type: ignore

def isfunction(fcn) -> bool:
    "Returns whether the object is a function"
    return isinstance(fcn, (LambdaType, FunctionType, MethodType, partial))

def parametercount(fcn) -> int:
    "return the number of *required* parameters"
    return sum(1 for j in inspect.signature(fcn).parameters.values()
               if j.kind == j.POSITIONAL_OR_KEYWORD and j.default is j.empty)

def ismethod(fcn) -> bool:
    "to be called in method decorators"
    if isinstance(fcn, cast(type, classmethod)):
        return True

    elif next(iter(signature(fcn).parameters), '') in ('self', 'cls', 'mcs'):
        return True

    return False

def getlocals(ind) -> dict:
    "returns the locals from a higher frame"
    return  inspect.stack()[ind+1][0].f_locals

def getclass(string:str) -> Optional[type]:
    "returns the class indicated by the string"
    if isinstance(string, str):
        mod  = string[:string.rfind('.')]
        attr = string[string.rfind('.')+1:]
        if attr[0] != attr[0].upper():
            __import__(string)
            return None

        return getattr(__import__(mod, fromlist = (attr,)), attr) # type: ignore
    return string
