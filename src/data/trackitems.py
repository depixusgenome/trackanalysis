#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Adds easy access to cycles and events"
from    types      import LambdaType, MethodType, FunctionType, GeneratorType
from    typing     import Optional, Tuple, Union, Any # pylint: disable=unused-import
from    typing     import List, Sequence, Iterable    # pylint: disable=unused-import
from    typing     import Iterator                    # pylint: disable=unused-import
from    copy       import copy as shallowcopy
from    functools  import wraps

import  numpy      # type: ignore

from    model      import levelprop, Level

def setfield(fcn):
    u"provides a setter return self"
    @wraps(fcn)
    def _wrap(self, item):
        name = fcn.__name__[len("with"):]
        setattr(self, name, item)
        return self
    return _wrap

def isfunction(fcn) -> bool:
    u"Returns whether the object is a function"
    return isinstance(fcn, (LambdaType, FunctionType, MethodType))

class TrackItems:
    u"Class for iterating over beads or creating a new list of data"
    def __init__(self, **kw) -> None:
        self.track     = kw.get('track',    None)   # type: ignore
        self.data      = kw.get('data',     None)   # type: Optional[Dict]
        self.selected  = None                       # type: Optional[List]
        self.discarded = None                       # type: Optional[List]
        self.actions   = kw.get('actions',  [])     # type: List
        self.parents   = kw.get('parents',  tuple())

        self.withdata  (self.data)
        self.selecting (kw.get('selected',   None))
        self.discarding (kw.get('discarded', None))
        self.withcopy   (kw.get('copy',      False))
        self.withsamples(kw.get('samples',   None))

    def withsamples(self, samples) -> 'TrackItems':
        u"specifies that only some samples should be taken"
        if samples is not None:
            self.actions.append(lambda item: (item[0], item[1][samples]))
        return self

    def withcopy(self, cpy:bool) -> 'TrackItems':
        u"specifies that a copy of the data should or shouldn't be made"
        npfcn = lambda item: (item[0], numpy.copy(item[1])) # type: ignore
        if cpy:
            self.actions.append(npfcn)
        else:
            self.actions.remove(npfcn)
        return self

    def withaction(self, fcn, clear = False) -> 'TrackItems':
        u"specifies that a copy of the data should or shouldn't be made"
        if clear:
            self.actions = []

        self.actions.append(fcn)
        return self

    def getaction(self):
        u"returns a function performing all actions"
        if len(self.actions) > 1:
            def _act(item):
                for action in self.actions:
                    item = action(item)
            return _act
        elif len(self.actions) == 1:
            return self.actions[0]
        else:
            return None

    @setfield
    def withdata(self, dat) -> 'TrackItems':
        u"sets the data"

    def _selection(self, attr, cyc, clear) -> 'TrackItems':
        if cyc is None or cyc is all:
            setattr(self, attr, None)
            return self

        if clear:
            setattr(self, attr, None)

        if getattr(self, attr) is None:
            setattr(self, attr, [])

        if isinstance(cyc, int) or isfunction(cyc):
            getattr(self, attr).append(cyc)
        else:
            getattr(self, attr).extend(cyc)

        if len(getattr(self, attr)) == 0:
            setattr(self, attr, None)
        return self

    def selecting(self, cyc, clear = False) -> 'TrackItems':
        u"selects ids over which to iterate. See class doc."
        return self._selection('selected', cyc, clear)

    def discarding(self, cyc, clear = False) -> 'TrackItems':
        u"selects ids to discard. See class doc."
        return self._selection('discarded', cyc, clear)

    @staticmethod
    def name(*args):
        u"returns a column name for a given id"
        return args

    def _unlazyfy(self):
        for name, val in self.__dict__.items():
            if isfunction(val):
                setattr(self, name, val())

        for attr in ('selected', 'discarded'):
            old = getattr(self, attr)
            if old is None or all(not isfunction(i) for i in old):
                continue

            method = getattr(self, attr[:-2]+'ing')
            method(None)
            for i in old:
                method(i() if isfunction(i) else i)

        if self.data is None:
            self.data = self.track.data

    def keys(self) -> 'Iterator':
        u"returns accepted keys"
        self._unlazyfy()

        if self.discarded is None:
            yield from (key for key in self._keys(self.selected))
        else:
            disc = frozenset(self._keys(self.discarded))
            yield from (key for key in self._keys(self.selected) if key not in disc)

    def __iter__(self) -> 'Iterator[Tuple[Any, Sequence[float]]]':
        self._unlazyfy()
        act = self.getaction()
        if act is None:
            yield from (col      for col in self._iter())
        else:
            yield from (act(col) for col in self._iter())

    def __getitem__(self, keys):
        self._unlazyfy()
        if isinstance(keys, slice):
            return shallowcopy(self).withsamples(keys)
        elif isinstance(keys, (list, GeneratorType)):
            return shallowcopy(self).selecting(keys, clear = True)
        else:
            return next(shallowcopy(self).selecting(keys, clear = True))[1]

    def _keys(self, sel:'Optional[Sequence]') -> 'Iterable':
        if sel is None:
            yield from (i for i in self.data.keys())
        else:
            keys = frozenset(self.data.keys())
            yield from (i for i in sel if i in keys)

    def _iter(self) -> 'Iterator[Tuple[Any,Any]]':
        yield from ((bead, self.data[bead]) for bead in self.keys())

@levelprop(Level.track)
class Beads(TrackItems):
    u"""
    Class for iterating over beads:

    * providing all: selects all beads

    * providing names or ids: selects only those columns
    """
    def _keys(self, sel):
        if sel is None:
            isbead = self.track.isbeadname
            yield from (i for i in self.data.keys() if isbead(i))
        else:
            yield from (i for i in sel              if i in self.data.keys())

    def _iter(self):
        yield from ((bead, self.data[bead]) for bead in self.keys())

@levelprop(Level.bead)
class Cycles(TrackItems):
    u"""
    Class for iterating selected cycles:

    * providing a pair (column name, cycle id) will extract a cycle on
      this column only.

    * providing a pair (column name, all) will extract all cycles for a given bead.

    * providing with a unique cycle id will extract all columns for that cycle
    """
    def __init__(self, **kw) -> None:
        super().__init__(**kw)
        self.first = kw.get('first', None)   # type: Optional[int]
        self.last  = kw.get('last',  None)   # type: Optional[int]

    def withphases(self, first, last) -> 'Cycles':
        u"specifies the phase to extract: None for all"
        self.first = first
        self.last  = last
        return self

    @setfield
    def withfirst(self, first) -> 'Cycles':
        u"specifies the phase to extract: None for all"

    @setfield
    def withlast(self, last) -> 'Cycles':
        u"specifies the phase to extract: None for all"

    def _keys(self, sel) -> 'Iterable[Tuple[Union[str,int], int]]':
        allcycles = lambda: range(self.track.ncycles)
        beads     = tuple(Beads(track = self.track, data = self.data).keys())
        allcols   = frozenset(self.data.keys())
        if sel is None:
            yield from ((col, cid) for col in beads for cid in allcycles())
            return

        for thisid in sel:
            if isinstance(thisid, (tuple, list)):
                bid, tmp = thisid[0], thisid[1] # type: Union[str,int], Any
                if bid not in allcols:
                    continue

                if tmp is all:
                    yield from ((bid, cid) for cid in allcycles())

                elif isinstance(tmp, int):
                    yield (bid, tmp)

            elif thisid is all:
                yield from ((col, cid) for col in beads for cid in allcycles())

            else:
                yield from ((col, thisid) for col in beads)

    def _iter(self):
        ncycles = self.track.ncycles
        nphases = self.track.nphases
        phaseid = self.track.phaseid

        first   = 0       if self.first is None else self.first
        last    = nphases if self.last  is None else self.last+1

        def _getdata(bid:int, cid:int):
            ind1 = phaseid(cid, first)
            if last == nphases:
                ind2 = None if cid >= ncycles else phaseid(cid+1, 0)
            else:
                ind2 = phaseid(cid, last)

            return self.name(bid, cid), self.data[bid][ind1:ind2]

        yield from (_getdata(bid, cid) for bid, cid in self.keys())
