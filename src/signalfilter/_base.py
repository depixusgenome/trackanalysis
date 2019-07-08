#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Signal Analysis: filters for removing noise"
from typing         import (Union, Iterator, Iterable, Tuple, Sequence, Optional,
                            overload, cast, TYPE_CHECKING)

import numpy as np

from utils          import initdefaults
from utils.rescaler import Rescaler, ARescaler
# pylint: disable=no-name-in-module,import-error
from ._core.stats   import (hfsigma, mediandeviation, nanhfsigma as _nanhfsigma,
                            nanmediandeviation as _nanmediandeviation)

if TYPE_CHECKING:
    # pylint: disable=unused-import
    from data.track import Track
    from data.views import TrackView

def _add_doc(other):
    def _wrapper(fcn):
        if getattr(fcn, '__doc__', None):
            fcn.__doc__ += "\n\n"+getattr(other, '__doc__', '')
        return fcn
    return _wrapper

@_add_doc(hfsigma)
def nanhfsigma(arr: np.ndarray, ranges = None, sampling: int = 1)->float:
    "hfsigma which takes care of nans."
    arr = np.asarray(arr).ravel()
    if len(arr) and not np.isscalar(arr[0]):
        arr = np.float32(arr) # type: ignore
    return _nanhfsigma(arr, ranges, sampling)

@_add_doc(mediandeviation)
def nanmediandeviation(arr: np.ndarray, ranges = None) -> float:
    "mediandeviation which takes care of nans."
    arr = np.asarray(arr).ravel()
    if len(arr) and not np.isscalar(arr[0]):
        arr = np.float32(arr) # type: ignore
    return _nanmediandeviation(arr, ranges)

BEADKEY   = Union[str,int]
DATATYPE  = Union[Sequence[Sequence[np.ndarray]],
                  Sequence[np.ndarray],
                  np.ndarray,
                  None]
PRECISION = Union[float, Tuple[DATATYPE, int], None]

class PrecisionAlg(ARescaler):
    "Implements precision extraction from data"
    precision: Optional[float] = None
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

        if precision is not None and np.isscalar(precision) and precision > 0.:
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

class CppPrecisionAlg(Rescaler):
    "Implements precision extraction from data: use only in case of Metaclass conflict"
    precision    = PrecisionAlg.precision
    rawfactor    = PrecisionAlg.rawfactor
    MINPRECISION = PrecisionAlg.MINPRECISION
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

        prec = cast(float, precision)
        if np.isscalar(prec) and prec > 0.:
            return max(self.MINPRECISION, float(prec))

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
