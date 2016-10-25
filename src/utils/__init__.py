#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"utils"
from typing         import Callable, cast
from types          import LambdaType, FunctionType, MethodType
from contextlib     import contextmanager
from inspect        import signature


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
