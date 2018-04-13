#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=invalid-name
"utils for inspecting objects and frames"
import inspect
from   functools import partial
from   pickle    import dumps
from   types     import LambdaType, FunctionType, MethodType
from   typing    import Optional, cast

signature           = inspect.signature
getmembers          = inspect.getmembers
isgeneratorfunction = inspect.isgeneratorfunction

def templateattribute(cls, index) -> type:
    "returns a template attribute"
    if not isinstance(cls, type):
        cls = type(cls)
    cur  = cls
    if getattr(cur, '__args__', None):
        return cur.__args__[index]    # type: ignore

    orig = getattr(cls, '__orig_bases__')
    while orig is None or orig[0].__args__ is None:
        cur  = getattr(cur, '__base__')
        orig = getattr(cur, '__orig_bases__', None)
    return orig[0].__args__[index]    # type: ignore


def diffobj(left, right):
    "return a dictionnary of attributes in `left` which differ from `right`"
    if not isinstance(right, type(left)):
        raise TypeError(f"{left} and {right} are different classes")

    if isinstance(left, dict):
        dleft = left
    elif hasattr(left, '__getstate__'):
        dleft = left.__getstate__()
        if not isinstance(dleft, dict):
            raise NotImplementedError()
    else:
        dleft = left.__dict__()

    itr = ((i, j, getattr(right, i)) for i, j in dleft.items())
    return {i: j for i, j, k in itr if j != k and dumps(j) != dumps(k)}

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
