#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Signal Analysis: filters for removing noise"
# pylint: disable=no-name-in-module,import-error
from typing     import Union
from functools  import wraps
from pandas     import Series
from utils      import kwargsdefaults
from ._core     import ForwardBackwardFilter, NonLinearFilter

def _m_correct_pybind11_bug(cls):
    old = cls.__init__
    @wraps(old)
    def __init__(self, __old__ = old, **kwa):
        __old__(self, kwa)
    cls.__init__ = __init__

    old = cls.__call__
    @wraps(old)
    def __call__(self, inp, __old__ = old, **kwa):
        __old__(self, inp, kwa)
    cls.__call__ = __call__

_m_correct_pybind11_bug(ForwardBackwardFilter)
_m_correct_pybind11_bug(NonLinearFilter)

class RollingFilter:
    u"interface to panda rolling window methods"
    def __init__(self, window = 10, mode = 'mean', std = None, **_):
        self.window = window
        self.std    = std
        self.mode   = mode

    def __call__(self, data):
        series = Series(data).rolling(self.window, center = True)
        imin   = self.window//2 + (self.window % 2)
        imax   = -self.window//2

        if self.mode in ('gaussian', 'kaiser'):
            if self.std is None:
                raise AttributeError("'gaussian' and 'kaiser' modes need an std")
            data[imin:imax] = getattr(series, self.mode)(std = self.std).values
        else:
            data[imin:imax] = getattr(series, self.mode)().values
        return data

Filter = Union[RollingFilter,NonLinearFilter,ForwardBackwardFilter]
