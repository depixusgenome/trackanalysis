#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Signal Analysis: filters for removing noise"
# pylint: disable=no-name-in-module,import-error
from typing         import Union, Iterator, Tuple, Optional, Sequence, cast
from itertools      import chain

import numpy as np

from utils          import initdefaults
from ._core.stats   import hfsigma

def nanhfsigma(arr: np.ndarray):
    u"hfsigma which takes care of nans"
    arr = arr.ravel()
    if len(arr) == 0:
        return

    if not np.isscalar(arr[0]):
        arr = np.float32(arr) # type: ignore
    return hfsigma(arr[~np.isnan(arr)])

class PrecisionAlg:
    u"Implements precision extraction from data"
    DATATYPE  = Union[Sequence[Sequence[np.ndarray]],
                      Sequence[np.ndarray],
                      np.ndarray,
                      None]
    precision = None # type: Optional[float]
    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        pass

    def getprecision(self,                  # pylint: disable=too-many-branches
                     precision:Optional[float] = None,
                     data     :DATATYPE        = tuple(),
                     beadid                    = None) -> float:
        u"""
        Returns the precision, possibly extracted from the data.
        Raises AttributeError if the precision was neither set nor could be
        extracted
        """

        if precision is None:
            precision = self.precision

        if np.isscalar(precision) and precision > 0.:
            return float(precision)

        if beadid is not None:
            return cast(float, self.rawprecision(data, beadid))

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

    @classmethod
    def rawprecision(cls, track, ibead) -> Union[float, Iterator[Tuple[int, float]]]:
        u"Obtain the raw precision for a given bead"
        track = getattr(track, 'track', track)
        cache = getattr(track, '_rawprecisions')
        val   = cache.get(ibead, None)

        if val is None:
            if isinstance(ibead, int):
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
