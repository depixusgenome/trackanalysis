#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"easy access to beads"
from   typing import (TYPE_CHECKING, Iterator, Optional, Sequence, Tuple,
                      Union, cast)
from   copy   import copy as shallowcopy
import numpy  as     np
from   ._dict import BEADKEY, isellipsis, isint
from   ._view import TrackView, ITrackView, Level

class Beads(TrackView, ITrackView):
    """
    ### Slicing Methods

    One can:

    * iterate over a selection of beads:

        * `track.beads[[1, 5]]` to select beads 1 and 5
        * `track.beads[1:5]` to select beads from 1 to 5

    * iterate over cycles: `track.beads[:,:]` returns a `Cycles` object
    """
    __doc__ =  TrackView.__format_doc__(__doc__,
                                        itercode   = """
        >>> for ibead, data in track.beads:
        ...     assert isinstance(ibead,  int)
        ...     assert isinstance(data,   np.array)""",
                                        actioncode = """
        >>> def myfunction(frame: Bead, info: Tuple[int, np.ndarray]
        ...               ) -> Tuple[int, np.ndarray]:
        ...     return info[0], 1.5 * info[1]
        >>> track.beads.withaction(myfunction)""",
                                        chaincode  = """
        >>> (track.beads
        ...  .withsample(slice(10, 100, 2))
        ...  .withaction(lambda _, i: (i[0], sum(i[1])))""",
                                        datadescr  = """
        Each iteration returns a the bead number and the data for that bead:""",
                                        selecting  = """
        * `selecting` allows selecting specific beads:

            * `track.cycles.selecting(1)` selects bead 1
            * `track.cycles.selecting([1, 2])` selects bead 1 and 2""",
                                        views      = "beads")

    level         = Level.bead
    cycles: slice = None
    def __init__(self, **kwa):
        super().__init__(self, **kwa)
        self.__withcycles(kwa.get('cycles', ...))

    def _keys(self, sel:Optional[Sequence], beadsonly: bool) -> Iterator[BEADKEY]:
        if isinstance(self.data, Beads):
            if sel is None:
                yield from self.data.keys(None, beadsonly)
            else:
                yield from (i for i in self.data.keys(None, beadsonly) if i in sel)
        else:
            yield from super()._keys(sel, beadsonly)

    def _iter(self, sel = None) -> Iterator[Tuple[BEADKEY, np.ndarray]]:
        if isinstance(self.data, Beads) and self.cycles is None:
            beads = cast(Beads, self.data)
            if sel is None:
                sel = self.selected

            if sel is None:
                yield from beads.__iter__() # pylint: disable=no-member

            elif beads.selected:
                parent = frozenset(beads.keys())
                sel    = [i for i in shallowcopy(beads).selecting(sel, True).keys()
                          if i in parent]
            yield from shallowcopy(beads).selecting(sel, clear = True).__iter__()
            return

        itr = ((bead, self.data[bead]) for bead in self.keys(sel))
        if self.cycles is not None:
            cyc  = self.cycles
            def _get(arr):
                ind1 = None if cyc.start is None else self.track.phases[cyc.start,0]
                ind2 = None if cyc.stop  is None else self.track.phases[cyc.stop, 0]
                return arr[ind1:ind2]
            itr = ((bead, _get(arr)) for bead, arr in itr)

        yield from itr

    def __getitem__(self, keys) -> Union['Beads',np.ndarray]:
        if isinstance(keys, tuple):
            if len(keys) == 2:
                if isinstance(self.cycles, slice):
                    cpy = shallowcopy(self).withcycles(...) # don't select cycles twice
                    res = self.track.cycles.new(data = cpy)
                    if all(isellipsis(i) for i in keys):
                        return res.selecting([(..., i) for i in self.cyclerange()])
                    if isellipsis(keys[1]):
                        return res.selecting([(keys[0], i) for i in self.cyclerange()])
                    if keys[1] not in self.cyclerange():
                        return res.new(data = {}, direct = True)
                    return res[keys]
                res = self.track.cycles.new(data = self)
                return res if all(isellipsis(i) for i in keys) else res[keys]
            raise NotImplementedError()
        return super().__getitem__(keys)

    def cyclerange(self) -> range:
        "returns the range of available cycles"
        start = getattr(self.cycles, 'start', 0)
        if start is None:
            start = 0

        stop = getattr(self.cycles, 'stop', None)
        if stop is None:
            stop = self.track.ncycles
        return range(start, stop)

    def withcycles(self, cyc) -> 'Beads':
        "specifies that only some cycles should be taken"
        return self.__withcycles(cyc)

    @staticmethod
    def isbead(key) -> bool:
        "returns whether the key is one for a bead"
        return isint(key)

    def __withcycles(self, cyc) -> 'Beads':
        "specifies that only some cycles should be taken"
        if cyc is None or cyc is Ellipsis:
            self.cycles = None
            return self

        if isinstance(cyc, range):
            cyc = slice(cyc.start, cyc.stop, cyc.step) # type: ignore

        if cyc.step not in (1, None):
            raise NotImplementedError()
        self.cycles = cyc
        return self

    if TYPE_CHECKING:
        def keys(self,
                 sel      :Optional[Sequence] = None,
                 beadsonly:Optional[bool]     = None) -> Iterator[BEADKEY]:
            yield from super().keys(sel, beadsonly)

        def __iter__(self) -> Iterator[Tuple[BEADKEY, np.ndarray]]:
            yield from super().__iter__()
