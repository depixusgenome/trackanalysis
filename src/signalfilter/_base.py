#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Signal Analysis: filters for removing noise"
# pylint: disable=no-name-in-module,import-error
from typing         import Union, Iterator, Tuple, Sequence, cast
from itertools      import chain

import numpy as np

from utils          import initdefaults
from ._core.stats   import hfsigma      # pylint: disable=import-error

def nanhfsigma(arr: np.ndarray):
    "hfsigma which takes care of nans"
    arr = arr.ravel()
    if len(arr) == 0:
        return

    if not np.isscalar(arr[0]):
        arr = np.float32(arr) # type: ignore
    return hfsigma(arr[~np.isnan(arr)])

DATATYPE  = Union[Sequence[Sequence[np.ndarray]],
                  Sequence[np.ndarray],
                  np.ndarray,
                  None]
PRECISION = Union[float, Tuple[DATATYPE, int], None]

class PrecisionAlg:
    "Implements precision extraction from data"
    precision = None # type: float
    rawfactor = 1.
    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        pass

    def getprecision(self, # pylint: disable=too-many-branches
                     precision:PRECISION = None,
                     data     :DATATYPE  = tuple(),
                     beadid   :int       = None) -> float:
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
            return cast(float, self.rawprecision(data, beadid))*self.rawfactor

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

    @classmethod
    def rawprecision(cls, track, ibead) -> Union[float, Iterator[Tuple[int, float]]]:
        "Obtain the raw precision for a given bead"
        track = getattr(track, 'track', track)
        cache = getattr(track, '_rawprecisions')
        val   = cache.get(ibead, None)

        if val is None:
            if np.isscalar(ibead):
                beads        = track.beads
                cache[ibead] = val = nanhfsigma(beads[ibead])
            else:
                if ibead is None or ibead is Ellipsis:
                    beads = track.beadsonly
                    ibead = set(beads.keys())
                else:
                    beads = track.beads
                    ibead = set(ibead)

                if len(ibead-set(cache)) > 0:
                    cache.update((i, nanhfsigma(beads[i])) for i in ibead-set(cache))
                val = iter((i, cache[i]) for i in ibead)
        return val
