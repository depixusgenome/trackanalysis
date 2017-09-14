#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Signal Analysis: filters for removing noise"
# pylint: disable=no-name-in-module,import-error
from typing     import Union
#from functools  import wraps
from pandas     import Series
from ._core     import ForwardBackwardFilter, NonLinearFilter # pylint: disable=import-error

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
