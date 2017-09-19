#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"easy access to cycles"
from   typing import (TYPE_CHECKING, Iterator, # pylint: disable=unused-import
                      Callable, Optional, Sequence, Tuple, Dict, Iterable,
                      Union, Any, cast)
from   copy   import copy as shallowcopy
import numpy  as     np

from   utils  import initdefaults, isfunction
from   ._dict import (BEADKEY, CYCLEKEY,       # pylint: disable=unused-import
                      isellipsis, isint)
from   ._view import TrackView, ITrackView, Level

_m_NONE  = type('_m_NONE', (), {})             # pylint: disable=invalid-name

class Cycles(TrackView, ITrackView):
    """
    Class for iterating over selected cycles:

    * providing a pair (column name, cycle id) will extract a cycle on
      this column only.

    * providing a pair (column name, all) will extract all cycles for a given bead.

    * providing with a unique cycle id will extract all columns for that cycle
    """
    level      = Level.cycle
    first: int = None
    last:  int = None
    _direct    = False  # type: bool

    @initdefaults(frozenset(locals()),
                  direct = lambda i, j: setattr(i, '_direct', j))
    def __init__(self, **kw):
        super().__init__(**kw)

    @property
    def direct(self) -> bool:
        "whether the data keys are directly cycle keys"
        return (self._direct or isinstance(self.data, dict)
                and len(self.data) > 0
                and isinstance(next(iter(self.data)), tuple))

    @direct.setter
    def direct(self, i:bool):
        "whether the data keys are directly cycle keys"
        self._direct = i

    def __keysfrombeads(self, sel, beadsonly):
        beads     = tuple(self.track.beads.new(data = self.data).keys(None, beadsonly))
        allcycles = range(self.track.ncycles)
        if sel is None:
            yield from ((col, cid) for col in beads for cid in allcycles)
            return

        isbead = self.track.beads.isbead
        for thisid in sel:
            if isellipsis(thisid):
                yield from ((col, cid) for col in beads for cid in allcycles)

            elif np.isscalar(thisid):
                yield from ((thisid, cid) for cid in allcycles)

            else:
                bid, tmp = thisid[0], thisid[1] # type: BEADKEY, Any
                if isellipsis(bid) and isellipsis(tmp):
                    yield from ((col, cid) for col in beads for cid in allcycles)
                elif isellipsis(bid):
                    yield from ((bid, tmp) for bid in beads)
                elif beadsonly and not isbead(bid):
                    continue
                elif isellipsis(tmp):
                    yield from ((bid, cid) for cid in allcycles)
                else:
                    yield (bid, tmp)

    def __keysdirect(self, sel, beadsonly):
        if beadsonly:
            isbead = self.isbead
            yield from (i for i in self.__keysdirect(sel, False) if isbead(i))

        if sel is None:
            yield from self.data.keys()
            return

        keys = list(self.data.keys())
        for thisid in sel:
            if isellipsis(thisid):
                yield from keys
            elif np.isscalar(thisid):
                yield from (i for i in keys if i[0] == thisid)
            else:
                bid, tmp = thisid[0], thisid[1] # type: BEADKEY, Any
                if isellipsis(bid) and isellipsis(tmp):
                    yield from keys
                elif isellipsis(bid):
                    yield from (i for i in keys if i[1] == tmp)
                elif isellipsis(tmp):
                    yield from (i for i in keys if i[0] == bid)
                else:
                    yield (bid, tmp)

    def _keys(self, sel, beadsonly) -> Iterable[CYCLEKEY]:
        if isinstance(self.data, Cycles):
            data = cast(Cycles, self.data)
            if sel is None:
                yield from data.keys(None, beadsonly)
            else:
                yield from self.__keysdirect(sel, beadsonly)

        elif self.direct:
            yield from self.__keysdirect(sel, beadsonly)
        else:
            yield from self.__keysfrombeads(sel, beadsonly)

    def __iterfrombeads(self, sel = None):
        ncycles = self.track.ncycles
        nphases = self.track.nphases
        phase   = self.track.phase

        first   = 0       if self.first is None else self.first
        last    = nphases if self.last  is None else self.last+1

        data    = {} # type: Dict[BEADKEY, np.ndarray]
        def _getdata(bid:int, cid:int):
            bead = data.get(bid, None)
            if bead is None:
                data[bid] = bead = self.data[bid]

            ind1 = phase(cid, first)
            ind2 = (phase(cid, last) if last  < nphases else
                    (phase(cid+1, 0) if cid+1 < ncycles else None))

            return (bid, cid), bead[ind1:ind2]

        yield from (_getdata(bid, cid) for bid, cid in self.keys(sel))

    def _iter(self, sel = None) -> Iterator[Tuple[CYCLEKEY, np.ndarray]]:
        if isinstance(self.data, Cycles):
            cycles = cast(Cycles, self.data)
            if sel is None:
                sel = self.selected

            if sel is None:
                yield from cycles.__iter__() # pylint: disable=no-member
                return
            elif cycles.selected:
                parent = frozenset(cycles.keys())
                sel    = [i for i in shallowcopy(cycles).selecting(sel, True).keys()
                          if i in parent]
            yield from shallowcopy(cycles).selecting(sel, clear = True).__iter__()

        elif self.direct:
            yield from ((key, self.data[key]) for key in self.keys(sel))

        else:
            yield from self.__iterfrombeads(sel)

    def withphases(self,
                   first:Union[int,Tuple[int,int],None],
                   last:Union[int,None,type] = _m_NONE) -> 'Cycles':
        "specifies the phase to extract: None or ... for all"
        if isinstance(first, tuple):
            self.first, self.last = first
        elif last is _m_NONE:
            self.first = first
            self.last  = first
        else:
            self.first = first
            self.last  = cast(Optional[int], last)
        if self.first is Ellipsis:
            self.first = None
        if self.last is Ellipsis:
            self.last = None
        return self

    def withfirst(self, first:Optional[int]) -> 'Cycles':
        "specifies the phase to extract: None for all"
        self.first = first
        return self

    def withlast(self, last:Optional[int]) -> 'Cycles':
        "specifies the phase to extract: None for all"
        self.last = last
        return self

    def phase(self, cid:Optional[int] = None, pid:Optional[int] = None):
        "returns phase ids for the given cycle"
        vect = self.track.phases
        if isellipsis(cid) and isellipsis(pid):
            return vect         - vect[:,0]
        if isellipsis(cid):
            return vect[:,pid]  - vect[:,0]
        if isellipsis(pid):
            return vect[cid,:]  - vect[cid,0]
        return vect[cid,pid]- vect[cid,0]

    def maxsize(self):
        "returns the max size of cycles"
        if self.direct and self.first is None and self.last is None:
            return max((len(i) for i in self.data.values()), default = 0)

        if isfunction(self.track):
            self.track = cast(Callable, self.track)()

        first = self.track.phase(..., 0 if self.first is None else self.first)
        if self.last is None or self.last == self.track.nphases-1:
            return np.max(np.diff(first))
        last = self.track.phase(..., self.last+1)
        return np.max(last - first)

    @staticmethod
    def isbead(key:CYCLEKEY) -> bool:
        "returns whether the key is one for a bead"
        return isint(key[0])

    if TYPE_CHECKING:
        # pylint: disable=useless-super-delegation
        def __getitem__(self, keys) -> Union['Cycles',np.ndarray]:
            return super().__getitem__(keys)

        def keys(self,
                 sel      :Optional[Sequence] = None,
                 beadsonly:Optional[bool]     = None) -> Iterator[CYCLEKEY]:
            yield from super().keys(sel)

        def __iter__(self) -> Iterator[Tuple[CYCLEKEY, np.ndarray]]:
            yield from super().__iter__()
