#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"utils"
from typing         import Callable
from types          import LambdaType, FunctionType, MethodType
from contextlib     import contextmanager

def isfunction(fcn) -> bool:
    u"Returns whether the object is a function"
    return isinstance(fcn, (LambdaType, FunctionType, MethodType))
