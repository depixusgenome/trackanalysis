#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Signal Analysis: filters for removing noise"
# pylint: disable=no-name-in-module,import-error
from typing         import (Union, Iterator, Iterable, Tuple, Sequence, Optional,
                            overload, cast, TYPE_CHECKING)
from abc            import ABC

import numpy as np

from utils          import initdefaults
# pylint: disable=import-error
from ._core.stats   import (hfsigma, mediandeviation, nanhfsigma as _nanhfsigma,
                            nanmediandeviation as _nanmediandeviation)

if TYPE_CHECKING:
    # pylint: disable=unused-import
    from data.track import Track
    from data.views import TrackView

def nanhfsigma(arr: np.ndarray, ranges = None):
    "hfsigma which takes care of nans."
    arr = np.asarray(arr).ravel()
    if len(arr) and not np.isscalar(arr[0]):
        arr = np.float32(arr) # type: ignore
    if ranges is None:
        return _nanhfsigma(arr)
    return _nanhfsigma(arr, ranges)

if getattr(nanhfsigma, '__doc__', None):
    nanhfsigma.__doc__ += "\n\n"+hfsigma.__doc__ # pylint: disable=no-member

def nanmediandeviation(arr: np.ndarray, ranges = None):
    "mediandeviation which takes care of nans."
    arr = np.asarray(arr).ravel()
    if len(arr) and not np.isscalar(arr[0]):
        arr = np.float32(arr) # type: ignore
    return _nanmediandeviation(arr, ranges)

if getattr(nanmediandeviation, '__doc__', None):
    nanmediandeviation.__doc__ += "\n\n"+mediandeviation.__doc__ # pylint:disable=no-member

BEADKEY   = Union[str,int]
DATATYPE  = Union[Sequence[Sequence[np.ndarray]],
                  Sequence[np.ndarray],
                  np.ndarray,
                  None]
PRECISION = Union[float, Tuple[DATATYPE, int], None]

class PrecisionAlg(ABC):
    "Implements precision extraction from data"
    precision    = None # type: float
    rawfactor    = 1.
    MINPRECISION = .5e-3
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
            return max(self.MINPRECISION, float(precision))

        if beadid is not None:
            return max(self.MINPRECISION,
                       cast(float, self.rawprecision(data, beadid)) # type: ignore
                      )*self.rawfactor

        if isinstance(data, (float, int)):
            return max(self.MINPRECISION, float(data))

        if isinstance(data, (Sequence, np.ndarray)):
            if len(data) == 0:
                pass
            elif isinstance(data[0], (Sequence, np.ndarray)):
                if len(data) == 1:
                    return self.getprecision(PrecisionAlg, data[0], beadid)

                first = next((i for i in data if len(i)), None)
                if first is not None:
                    if isinstance(first, (Sequence, np.ndarray)):
                        ret = np.median(tuple(nanhfsigma(np.concatenate(list(i)))
                                              for i in data if len(i)))
                    else:
                        ret = np.median(tuple(nanhfsigma(i) for i in data if len(i)))
                    return max(self.MINPRECISION, ret)*self.rawfactor
            else:
                return max(self.MINPRECISION, nanhfsigma(data))*self.rawfactor

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
