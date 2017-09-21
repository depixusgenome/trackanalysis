#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Tasks related to peakfinding"
from typing                 import (Iterable, Iterator, Tuple, FrozenSet, Sequence,
                                    Optional)
from functools              import partial
import numpy as np

from model                  import Level
from data.views             import BEADKEY, TrackView, Beads, isellipsis
from .selector              import PeakSelector, Output as PeakOutput, PeaksArray

Output = Tuple[BEADKEY, Iterator[PeakOutput]]
class PeaksDict(TrackView):
    "iterator over peaks grouped by beads"
    level = Level.peak
    def __init__(self, *_, config = None, **kwa):
        assert len(_) == 0
        super().__init__(**kwa)
        if config is None:
            self.config = PeakSelector()
        elif isinstance(config, dict):
            self.config = PeakSelector(**config)
        else:
            assert isinstance(config, PeakSelector), config
            self.config = config

        self.__keys: FrozenSet[BEADKEY] = None

    def compute(self, ibead, precision: float = None) -> Iterator[PeakOutput]:
        "Computes values for one bead"
        vals = iter(i for _, i in self.data[ibead,...]) # type: ignore
        yield from self.config(vals, self._precision(ibead, precision))

    def index(self) -> 'PeaksDict':
        "Returns indexes at the same key and positions"
        return self.withaction(self.__index)

    def withmeasure(self, singles = np.nanmean, multiples = None) -> 'PeaksDict':
        "Returns a measure per events."
        if multiples is None:
            multiples = lambda x: singles(np.concatenate(x))
        return self.withaction(partial(self.__measure, singles, multiples))

    @classmethod
    def measure(cls, itm: PeaksArray, singles = np.nanmean, multiples = None) -> PeaksArray:
        "Returns a measure per events."
        if len(itm) == 0:
            return itm

        if multiples is None:
            multiples = lambda x: singles(np.concatenate(x))

        if isinstance(itm[0][1], PeaksArray):
            itm[:] = [(i, cls.__array2measure(singles, multiples, j)) for i, j in itm]
        else :
            itm[:] = cls.__array2measure(singles, multiples, itm)
        return itm

    @staticmethod
    def singles(arr: PeaksArray) -> np.ndarray:
        "returns an array indicating where single events are"
        return np.array([isinstance(i, (tuple, np.void)) for i in arr], dtype = 'bool')

    @staticmethod
    def multiples(arr: PeaksArray) -> np.ndarray:
        "returns an array indicating where single events are"
        return np.array([isinstance(i, (list, np.ndarray)) for i in arr], dtype = 'bool')

    @classmethod
    def __measure(cls, singles, multiples, _, info):
        return info[0], ((i, cls.__array2measure(singles, multiples, j)) for i, j in info[1])

    @classmethod
    def __index(cls, _, info):
        return info[0], ((i, cls.__array2range(j)) for i, j in info[1])


    @staticmethod
    def __array2measure(singles, multiples, arr):
        if arr.dtype == 'O':
            arr[:] = [None                  if i is None            else
                      singles  (i[1])       if isinstance(i, tuple) else
                      multiples(i['data'])
                      for i in arr[:]]
        else:
            arr['data'] = [singles(i) for i in arr['data']]
        return arr

    @staticmethod
    def __array2range(arr):
        if arr.dtype == 'O':
            return np.array([None                        if i is None            else
                             range(i[0], i[0]+len(i[1])) if isinstance(i, tuple) else
                             range(i[0][0], i[-1][0]+len(i[-1][1]))
                             for i in arr])
        return np.array([None                        if i is None            else
                         range(i[0], i[0]+len(i[1])) if np.isscalar(i[1][0]) else
                         range(i[0][0], i[-1][0]+len(i[-1][1]))
                         for i in arr])

    def _keys(self, sel:Sequence = None, _ = None) -> Iterator[BEADKEY]:
        if self.__keys is None:
            if isinstance(self.data, PeaksDict):
                self.__keys = frozenset(i for i in self.data.keys() if Beads.isbead(i))
            else:
                self.__keys = frozenset(i for i, _ in self.data.keys() if Beads.isbead(i))

        if sel is None:
            yield from self.__keys
        else:
            ids = tuple(self._transform_ids(sel))
            yield from (i for i in self.__keys if i in ids)

    @staticmethod
    def _transform_ids(sel: Iterable) -> Iterator[int]:
        for i in sel:
            if isinstance(i, tuple):
                if len(i) == 0:
                    continue
                elif len(i) == 2 and not isellipsis(i[1]):
                    raise NotImplementedError()
                elif len(i) > 2 :
                    raise KeyError(f"Unknown key {i} in PeaksDict")
                if np.isscalar(i[0]):
                    yield i[0]
                else:
                    yield from i[0]
            else:
                yield i

    def _iter(self, sel:Sequence = None) -> Iterator[Output]:
        if isinstance(self.data, PeaksDict):
            if sel is None:
                yield from iter(self.data)                          # type: ignore
            yield from ((i, j) for i, j in self.data if i in sel)   # type: ignore

        yield from ((bead, self.compute(bead)) for bead in self.keys(sel))

    def _precision(self, ibead: int, precision: Optional[float]):
        return self.config.getprecision(precision, getattr(self.data, 'track', None), ibead)
