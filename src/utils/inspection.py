#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=invalid-name
u"utils for inspecting objects and frames"
import inspect
from   typing import cast
from   types  import LambdaType, FunctionType, MethodType

signature           = inspect.signature
getmembers          = inspect.getmembers
isgeneratorfunction = inspect.isgeneratorfunction

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

def getlocals(ind) -> dict:
    u"returns the locals from a higher frame"
    return  inspect.stack()[ind+1][0].f_locals
