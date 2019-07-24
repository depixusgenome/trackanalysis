#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"easy access to cycles"
from   typing import (
    Iterator, Callable, Optional, Tuple, Dict, Iterable, Union, List, Any,
    overload, cast
)
from   copy   import copy as shallowcopy
import numpy  as     np

from   taskmodel.level import PHASE, PhaseArg, Phase
from   utils           import initdefaults, isfunction
from   ._dict          import BEADKEY, CYCLEKEY, isellipsis
from   ._view          import TrackView, ITrackView, Level

_none  = type('_none', (), {})

class Cycles(TrackView, ITrackView):
    """
    ### Slicing Methods

    One can iterate over a selection of cycles and beads:

        * `track.cycles[[1, 5], [2, 7]]` to beads 1 and 5 and their cycles 2 and 7
        * `track.cycles[:,:10]` to select all beads and their cycles 0 through 9
        * `track.cycles[:10,:]` to select beads 0 through 9 and all their cycles
    """
    __doc__ =  TrackView.__format_doc__(__doc__,
                                        itercode   = """
        >>> for (ibead, icycle), data in track.cycles:
        ...     assert isinstance(ibead,  int)
        ...     assert isinstance(icycle, int)
        ...     assert isinstance(data,   np.array)""",
                                        actioncode = """
        >>> def myfunction(frame: Cycle,
        ...                info: Tuple[Tuple[int, int], np.ndarray]
        ...               ) -> Tuple[Tuple[int, int], np.ndarray]:
        ...     return info[0], 1.5 * info[1]
        >>> track.cycles.withaction(myfunction)""",
                                        chaincode  = """
        >>> (track.cycles
        ...  .withphases(5)
        ...  .withsample(slice(10, 100, 2))
        ...  .withaction(lambda _, i: (i[0], sum(i[1])))""",
                                        datadescr  = """
        Each iteration returns a tuple, indicating the bead number and the cycle
        number, and the data for that cycle:""",
                                        selecting  = """
        * `selecting` allows selecting:

            * beads:

                * `track.cycles.selecting(1)` selects bead 1
                * `track.cycles.selecting([1, 2])` selects bead 1 and 2

            * cycles:

                * `track.cycles.selecting((..., 1))` selects cycle 1 for all beads
                * `track.cycles.selecting([(1,1), (1,2)])` selects bead 1 cycles 1 and 2""",
                                        views      = "cycles")

    level                = Level.cycle
    first: Optional[int] = None
    last:  Optional[int] = None
    _direct              = False

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

    def beadextension(self, ibead:BEADKEY) -> Optional[float]:
        """
        Return the median bead extension (phase 3 - phase 1)
        """
        if self.direct:
            return None
        data = cast(dict, self.data)
        arr  = data[ibead] if ibead in data else None
        return None if arr is None else self.track.beadextension(arr) # type: ignore

    def phaseposition(self, phase: int, ibead:BEADKEY) -> Optional[float]:
        """
        Return the median position for a given phase
        """
        if self.direct:
            return None
        data = cast(dict, self.data)
        arr  = data[ibead] if ibead in data else None
        return None if arr is None else self.track.phaseposition(phase, arr) # type: ignore

    def __keysfrombeads(self, sel):
        beads     = tuple(self.track.beads.new(data = self.data).keys(None))
        if hasattr(self.data, 'cyclerange'):
            allcycles = self.data.cyclerange()
        else:
            allcycles = range(self.track.ncycles)
        if sel is None:
            yield from ((col, cid) for col in beads for cid in allcycles)
            return

        for thisid in sel: # pylint: disable=too-many-nested-blocks
            if isellipsis(thisid):
                yield from ((col, cid) for col in beads for cid in allcycles)

            elif np.isscalar(thisid):
                yield from ((thisid, cid) for cid in allcycles)

            else:
                bid: BEADKEY = thisid[0]
                tmp: Any     = thisid[1]
                if isellipsis(bid) and isellipsis(tmp):
                    yield from ((col, cid) for col in beads for cid in allcycles)
                elif isellipsis(bid):
                    yield from ((bid, tmp) for bid in beads)
                elif isellipsis(tmp):
                    yield from ((bid, cid) for cid in allcycles)
                else:
                    yield (bid, tmp)

    def __keysdirect(self, sel):
        if sel is None:
            yield from self.data.keys()
            return

        keys = list(self.data.keys())
        for thisid in sel: # pylint: disable=too-many-nested-blocks
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

    def _keys(self, sel) -> Iterable[CYCLEKEY]:
        if isinstance(self.data, Cycles):
            data = cast(Cycles, self.data)
            if sel is None:
                yield from data.keys(None)
            else:
                yield from self.__keysdirect(sel)

        elif self.direct:
            yield from self.__keysdirect(sel)
        else:
            yield from self.__keysfrombeads(sel)

    def __iterfrombeads(self, sel = None):
        first   = 0                  if self.first is None else self.first
        last    = self.track.nphases if self.last  is None else self.last+1
        phase   = self.track.phase.select(..., (first, last))
        data: Dict[BEADKEY, np.ndarray] = {}
        def _getdata(bid:int, cid:int):
            bead = data.get(bid, None)
            if bead is None:
                data[bid] = bead = self.data[bid]
            return (bid, cid), bead[phase[cid,0]:phase[cid,1]]

        yield from (_getdata(bid, cid) for bid, cid in self.keys(sel))

    def _iter(self, sel = None) -> Iterator[Tuple[CYCLEKEY, np.ndarray]]:
        if isinstance(self.data, Cycles):
            cycles = cast(Cycles, self.data)
            if sel is None:
                sel = self.selected

            if sel is None:
                yield from cycles.__iter__() # pylint: disable=no-member
                return
            if cycles.selected:
                parent = frozenset(cycles.keys())
                sel    = [i for i in shallowcopy(cycles).selecting(sel, True).keys()
                          if i in parent]
            yield from shallowcopy(cycles).selecting(sel, clear = True).__iter__()

        elif self.direct:
            tmp = cast(dict, self.data)
            yield from ((key, tmp[key]) for key in self.keys(sel))

        else:
            yield from self.__iterfrombeads(sel)

    def withphases(self,
                   first:Union[PhaseArg,Tuple[PhaseArg,PhaseArg],None],
                   last:Union[int,None,type] = _none) -> 'Cycles':
        "specifies the phase to extract: None or ... for all"
        if isinstance(first, tuple):
            first, last = first
        elif last is _none:
            last        = first

        phase      = self.phaseindex()
        self.first = None if first is Ellipsis else cast(int, phase[first])
        self.last  = None if last  is Ellipsis else cast(int, phase[last])
        return self

    def withfirst(self, first:Optional[int]) -> 'Cycles':
        "specifies the phase to extract: None for all"
        self.first = first
        return self

    def withlast(self, last:Optional[int]) -> 'Cycles':
        "specifies the phase to extract: None for all"
        self.last = last
        return self

    @overload
    @staticmethod
    def phaseindex() -> Phase:
        "return the PHASE object"

    @overload
    @staticmethod
    def phaseindex(__1:PhaseArg) -> int:
        "return the PHASE index"

    @overload
    @staticmethod
    def phaseindex(__1:PhaseArg, __2:PhaseArg, *args:PhaseArg) -> List[int]:
        "return the PHASE index"

    @staticmethod
    def phaseindex(*args:PhaseArg):
        "return the PHASE index"
        return PHASE if not args else PHASE[args[0]] if len(args) == 1 else PHASE[args]

    def phase(self, cid:Optional[int] = None, pid:Optional[PhaseArg] = None):
        "returns phase ids for the given cycle"
        if pid is None and isinstance(cid, str):
            pid, cid = cid, None
        isel  = isellipsis(cid), isellipsis(pid)
        if not isel[1]:
            pid = self.phaseindex()[pid]

        vect  = self.track.phases
        return (
            vect          - vect[:,0]   if all(isel) else
            vect[:,pid]   - vect[:,0]   if isel[0]   else
            vect[cid,:]   - vect[cid,0] if isel[1]   else
            vect[cid,pid] - vect[cid,0]
        )

    def maxsize(self):
        "returns the max size of cycles"
        if self.direct and self.first is None and self.last is None:
            return max((len(i) for i in self.data.values()), default = 0)

        if isfunction(self.track):
            self.track = cast(Callable, self.track)()

        first = self.track.phase.select(..., 0 if self.first is None else self.first)
        if self.last is None or self.last == self.track.nphases-1:
            return np.max(np.diff(first))
        last = self.track.phase.select(..., self.last+1)
        return np.max(last - first)
