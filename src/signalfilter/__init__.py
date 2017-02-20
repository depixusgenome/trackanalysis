#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Signal Analysis: filters, stats and interval detection"
# pylint: disable=no-name-in-module,import-error
from typing         import Union, Optional, Sequence, cast
from itertools      import chain

import numpy as np

from pandas         import Series
from utils          import initdefaults

from ._core         import (ForwardBackwardFilter, NonLinearFilter, samples)
from ._core.stats   import hfsigma

def nanhfsigma(arr: np.ndarray):
    u"hfsigma which takes care of nans"
    arr = arr.ravel()
    if len(arr) == 0:
        return

    if not np.isscalar(arr[0]):
        arr = np.float32(arr) # type: ignore
    return hfsigma(arr[~np.isnan(arr)])

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

class PrecisionAlg:
    u"Implements precision extraction from data"
    DATATYPE  = Union[Sequence[Sequence[np.ndarray]],
                      Sequence[np.ndarray],
                      np.ndarray,
                      None]
    precision = None # type: Optional[float]
    @initdefaults
    def __init__(self, **_):
        pass

    def getprecision(self,
                     precision:Optional[float] = None,
                     data     :DATATYPE        = tuple()) -> float:
        u"""
        Returns the precision, possibly extracted from the data.
        Raises AttributeError if the precision was neither set nor could be
        extracted
        """
        if precision is None:
            precision = self.precision

        if np.isscalar(precision) and precision > 0.:
            return float(precision)

        if isinstance(data, Sequence[Sequence[np.ndarray]]):
            if len(data) == 1:
                data = data[0]
            else:
                return np.median(tuple(nanhfsigma(i) for i in chain(iter(*data))))

        if (isinstance(data, Sequence[np.ndarray])
                and len(cast(np.ndarray, data[0]).shape) == 1):
            if len(data) == 1:
                data = data[0]
            else:
                return np.median(tuple(nanhfsigma(i) for i in data))

        if isinstance(data, (float, int)):
            return float(data)

        if isinstance(data, np.ndarray):
            return nanhfsigma(data)

        raise AttributeError('Could not extract precision: no data or set value')

Filter = Union[ForwardBackwardFilter, NonLinearFilter, RollingFilter]
