#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Signal Analysis: filters for removing noise"
# pylint: disable=no-name-in-module,import-error
from typing         import (Union, Iterator, Iterable, Tuple, Sequence, Optional,
                            overload, cast, TYPE_CHECKING)
from abc            import ABC
from itertools      import chain

import numpy as np

from utils          import initdefaults
from ._core.stats   import hfsigma, mediandeviation # pylint: disable=import-error

if TYPE_CHECKING:
    from data import Track, TrackView   # pylint: disable=unused-import

def _nanfcn(arr:np.ndarray, ranges, fcn):
    arr = arr.ravel()
    if len(arr) == 0:
        return

    if not np.isscalar(arr[0]):
        arr = np.float32(arr) # type: ignore

    fin = np.isfinite(arr)
    if ranges is None:
        return fcn(arr[fin])
    return np.nanmedian([fcn(arr[i:j][fin[i:j]]) for i, j in ranges])

def nanhfsigma(arr: np.ndarray, ranges = None):
    "hfsigma which takes care of nans."
    return _nanfcn(arr, ranges, hfsigma)
if nanhfsigma.__doc__:
    nanhfsigma.__doc__ += "\n\n"+hfsigma.__doc__ # pylint: disable=no-member

def nanmediandeviation(arr: np.ndarray, ranges = None):
    "mediandeviation which takes care of nans."
    return _nanfcn(arr, ranges, mediandeviation)
if nanmediandeviation.__doc__:
    nanmediandeviation.__doc__ += "\n\n"+mediandeviation.__doc__ # pylint:disable=no-member

BEADKEY   = Union[str,int]
DATATYPE  = Union[Sequence[Sequence[np.ndarray]],
                  Sequence[np.ndarray],
                  np.ndarray,
                  None]
PRECISION = Union[float, Tuple[DATATYPE, int], None]

class PrecisionAlg(ABC):
    "Implements precision extraction from data"
    precision = None # type: float
    rawfactor = 1.
    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        pass

    def getprecision(self, # pylint: disable=too-many-branches
                     precision:PRECISION = None,
                     data     :DATATYPE  = tuple(),
                     beadid   :BEADKEY   = None) -> float:
        """
        Returns the precision, possibly extracted from the data.  Raises
        AttributeError if the precision was neither set nor could be extracted
        """
        if isinstance(precision, tuple):
            data, beadid = precision
            precision    = self.precision

        elif precision is None:
            precision = self.precision

        if np.isscalar(precision) and precision > 0.:
            return float(precision)

        if beadid is not None:
            return cast(float, self.rawprecision(data, beadid))*self.rawfactor # type: ignore

        if isinstance(data, (float, int)):
            return float(data)

        if isinstance(data, (Sequence, np.ndarray)):
            if len(data) == 0:
                pass
            elif isinstance(data[0], (Sequence, np.ndarray)):
                if len(data) == 1:
                    return self.getprecision(PrecisionAlg, data[0], beadid)

                first = next((i for i in data if len(i)), None)
                if first is not None:
                    if isinstance(first, (Sequence, np.ndarray)):
                        ret = np.median(tuple(nanhfsigma(chain(*i)) for i in data if len(i)))
                    else:
                        ret = np.median(tuple(nanhfsigma(i) for i in data if len(i)))
                    return ret*self.rawfactor
            else:
                return nanhfsigma(data)*self.rawfactor

        raise AttributeError('Could not extract precision: no data or set value')

    # pylint: disable=unused-argument,function-redefined
    @overload
    @staticmethod
    def rawprecision(track:Union['TrackView', 'Track'], ibead: int) -> float:
        "Obtain the raw precision for a given bead"
        return 0.

    @overload
    @staticmethod
    def rawprecision(track:Union['TrackView', 'Track'],
                     ibead: Optional[Iterable[int]]
                    ) -> Iterator[Tuple[int,float]]:
        "Obtain the raw precision for a number of beads"

    @staticmethod
    def rawprecision(track, ibead, first = None, last = None):
        "Obtain the raw precision for a given bead"
        return getattr(track, 'track', track).rawprecision(ibead, first, last)
