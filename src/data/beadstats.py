#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Compute raw precision"
from typing       import (
    Dict, Union, Optional, Iterable, Iterator, Tuple, Callable, Type, TYPE_CHECKING,
    overload, cast
)

import numpy as np

from signalfilter import nanhfsigma, PrecisionAlg

if TYPE_CHECKING:
    from .track import Track
    from .views import Beads

def beadextension(track: 'Track', ibead: Union[int, np.ndarray], rng = (5., 95.)) -> float:
    """
    Return the median bead extension (phase 3 - phase 1)
    """
    phase = track.phase[...]
    inds  = [phase.initial, phase.pull+1]
    arr   = ibead if isinstance(ibead, np.ndarray) else track.data[ibead]
    bead  = np.split(arr, track.phases[:, inds].ravel() - track.phases[0,0])[1::2]
    vals  = [np.diff(np.nanpercentile(i, rng))[0] for i in bead if np.any(np.isfinite(i))]
    return np.nanmedian(vals) if len(vals) else np.NaN

def phaseposition(track, phase: int, ibead: Union[int, np.ndarray]) -> float:
    """
    Return the median position for a given phase
    """
    inds = [phase, phase+1]
    arr  = ibead if isinstance(ibead, np.ndarray) else track.data[ibead]
    bead = np.split(arr, track.phases[:, inds].ravel() - track.phases[0,0])[1::2]
    vals = [np.nanmedian(i) for i in bead if np.any(np.isfinite(i))]
    return np.nanmedian(vals) if len(vals) else np.NaN


RawPrecisionTypes = Union[Type['PhaseRangeRawPrecision'], Type['NormalizedRawPrecision']]


class RawPrecisionCache:
    "Stores the raw precision"
    __store__ = ('cache', '_computer')

    def __init__(self, tpe = None):
        self.cache:     Dict[int, float]  = {}
        self._computer: RawPrecisionTypes = PhaseRangeRawPrecision if tpe is None else tpe

    @property
    def computer(self) -> type:
        "the default computation type"
        return self._computer

    @computer.setter
    def computer(self, val: Union[RawPrecisionTypes, str]):
        "the default computation type"
        if isinstance(val, str):
            val = next(
                i
                for i in  (NormalizedRawPrecision, PhaseRangeRawPrecision)
                if val == getattr(i, 'keyword')()
            )

        if val not in (PhaseRangeRawPrecision, NormalizedRawPrecision):
            raise TypeError(f"Incorrect computer type {val}")

        if self._computer is not val:
            self._computer = cast(RawPrecisionTypes, val)
            self.cache.clear()

    @overload       # noqa: F811
    def get(
            self,
            track:  'Track',
            ibead:  int,
            phases: Union[None, Dict[int, float], Tuple[int, int]],
    ):
        "Obtain the raw precision for a given bead"

    @overload       # noqa: F811
    def get(
            self,
            track:  'Track',
            ibead:  Optional[Iterable[int]],
            phases: Union[None, Dict[int, float], Tuple[int, int]],
    ) -> Iterator[Tuple[int,float]]:
        "Obtain the raw precision for a number of beads"

    def get(        # noqa: F811
            self,
            track:  'Track',
            ibead:  Union[None, Iterable[int], int],
            phases: Union[None, Dict[int, float], Tuple[int, int]] = None
    ):
        """
        Obtain the raw precision for a given bead

        Parameters
        ----------
        ibead:
            An integer, sequence of integers or Ellipsis indicating for which bead
            to return results.
        phases:
            * if None: equivalent to phases == {1: .5, 3: .5}
            * if dictionary: the raw precision is the weighted average of hfsigma in
            the phases provided in the dictionnary.
            * if tuple: the raw precision is the hfsigma within the provided range
            of phases.

        Returns
        -------
        The raw precision for the bead(s).
        """
        cache = self.cache
        val   = (
            None if phases is not None or not np.isscalar(ibead) else
            self.cache.get(cast(int, ibead), None)
        )
        if val is None:
            beads = track.beads
            fcn   = self._computer.function(beads, phases)

            if np.isscalar(ibead):
                val = fcn(cast(int, ibead))
                if phases is None:
                    cache[cast(int, ibead)] = val
            else:
                keys = set(cast(
                    Iterable[int],
                    beads.keys() if ibead is None or ibead is Ellipsis else ibead
                ))
                if phases is not None:
                    return ((i, fcn(i)) for i in keys)

                if len(keys-set(cache)) > 0 and phases is None:
                    cache.update(
                        (i, fcn(i)) for i in keys-set(cache)
                    )
                return iter((i, cache[i]) for i in keys)
        return val

class PhaseRangeRawPrecision:
    """
    Computes the raw precision as the median over all cycles of the hfsigma on
    a given range of phases
    """
    __slots__ = ('beads', 'rate', 'phases')

    def __init__(self, beads: 'Beads', phases: Optional[Tuple[int, int]]):
        if phases is None:
            phases = beads.track.phase[...].initial, beads.track.phase[...].measure
        self.beads  = beads
        self.rate   = max(1, int(beads.track.framerate/_RAWPRECION_RATE+.5))
        inds        = beads.track.phases
        self.phases = [inds[:, phases[0]] - inds[0, 0], inds[:, phases[1]+1] - inds[0, 0]]

    @staticmethod
    def keyword() -> str:
        "return the keyword for this computation"
        return "range"

    def __call__(self, ibead: int) -> float:
        return max(
            PrecisionAlg.MINPRECISION,
            nanhfsigma(self.beads[ibead], zip(*self.phases), self.rate)
        )

    @classmethod
    def function(cls, beads, phase) -> Callable[[int], float]:
        "return an instance able to compute raw precisions"
        return cast(
            Callable[[int], float],
            (
                cls if isinstance(phase, tuple) or phase is None else NormalizedRawPrecision
            )(beads, phase)
        )

class NormalizedRawPrecision:
    """
    Computes the raw precision as the weighted average of the median over all
    cycles of the hfsigma computed for given phases
    """
    __slots__ = ('beads', 'rate', 'phases')

    def __init__(self, beads: 'Beads', phases: Optional[Dict[int, float]]):
        if phases is None:
            names  = beads.track.phase[...]
            phases = dict.fromkeys((names.initial, names.pull, names.measure), 1/3)

        self.beads  = beads
        self.rate   = max(1, int(beads.track.framerate/_RAWPRECION_RATE+.5))
        inds        = beads.track.phases
        self.phases = [
            ((inds[:,i] - inds[0, 0], inds[:,i+1] - inds[0, 0]), j)
            for i, j in phases.items()
        ]

    @staticmethod
    def keyword() -> str:
        "return the keyword for this computation"
        return "normalized"

    def __call__(self, ibead: int) -> float:
        return max(
            PrecisionAlg.MINPRECISION,
            sum(nanhfsigma(self.beads[ibead], zip(*i), self.rate)*j for i, j in self.phases)
        )

    @classmethod
    def function(cls, beads, phase) -> Callable[[int], float]:
        "return an instance able to compute raw precisions"
        return cast(
            Callable[[int], float],
            (
                cls if isinstance(phase, dict) or phase is None else PhaseRangeRawPrecision
            )(beads, phase)
        )


_RAWPRECION_RATE: float = 10.
