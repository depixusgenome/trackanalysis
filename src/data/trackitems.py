#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Adds easy access to cycles and events"
from    copy        import copy as shallowcopy
from    abc         import ABCMeta, abstractmethod
from    functools   import wraps
from    typing      import (Optional, Tuple, Union, # pylint: disable=unused-import
                            Any, List, Sequence, Iterable, Iterator)
import  numpy as np          # type: ignore

from    utils       import isfunction
from    model       import Level

_ALL   = frozenset((None, all, Ellipsis))
_INDEX = (tuple, int, str)

def setfield(fcn):
    u"provides a setter return self"
    @wraps(fcn)
    def _wrap(self, item):
        name = fcn.__name__[len("with"):]
        setattr(self, name, item)
        return self
    return _wrap

class Items(metaclass=ABCMeta):
    u"Class for iterating over data"

    def __init__(self, **_) -> None:
        super().__init__()
    @abstractmethod
    def __iter__(self) -> 'Iterator[Tuple[Any,Any]]':
        u"iterates over keys and data"

    @abstractmethod
    def __getitem__(self, val):
        u"can return one item or a copy of self with only the selected keys"

    @abstractmethod
    def keys(self, sel = None):
        u"iterates over keys"

class TrackItems(Items):
    u"Class for iterating over beads or creating a new list of data"
    level = Level.none
    def __init__(self, **kw) -> None:
        super().__init__()
        self.track     = kw.get('track',    None)   # type: ignore
        self.data      = kw.get('data',     None)   # type: Optional[Dict]
        self.selected  = None                       # type: Optional[List]
        self.discarded = None                       # type: Optional[List]
        self.actions   = kw.get('actions',  [])     # type: List
        self.parents   = kw.get('parents',  tuple())

        self.withdata   (self.data)
        self.selecting  (kw.get('selected',  None))
        self.discarding (kw.get('discarded', None))
        self.withcopy   (kw.get('copy',      False))
        self.withsamples(kw.get('samples',   None))

    def __copy__(self):
        return self.__class__(track = self.track,
                              **{i: shallowcopy(j)
                                 for i, j in self.__dict__.items() if i != 'track'})

    @staticmethod
    def copy(item):
        u"Copies the data"
        return item[0], np.copy(item[1])

    def withsamples(self, samples) -> 'TrackItems':
        u"specifies that only some samples should be taken"
        if samples is not None:
            self.actions.append(lambda item: (item[0], item[1][samples]))
        return self

    def withcopy(self, cpy:bool) -> 'TrackItems':
        u"specifies that a copy of the data should or shouldn't be made"
        if cpy:
            self.actions.append(self.copy)
        elif self.copy in self.actions:
            self.actions.remove(self.copy)
        return self

    def withfunction(self, fcn = None, clear = False, beadonly = False) -> 'TrackItems':
        u"Adds an action with fcn taking a value as single argument"
        if clear:
            self.actions = []

        if fcn is None:
            return self

        if beadonly:
            @wraps(fcn)
            def _action(key, val):
                return key, (fcn(val) if self._isbead(key) else val)
            self.actions.append(_action)
        else:
            self.actions.append(lambda key, val: (key, fcn(val)))
        return self

    def withaction(self, fcn = None, clear = False, beadonly = False) -> 'TrackItems':
        u"Adds an action with fcn taking a key and its values  as arguments"
        if clear:
            self.actions = []

        if fcn is None:
            return self

        if beadonly:
            @wraps(fcn)
            def _action(key, val):
                return fcn(key, val) if self._isbead(key) else val
            self.actions.append(_action)
        else:
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

    @staticmethod
    def _isbead(_):
        return True

    def _selection(self, attr, cyc, clear) -> 'TrackItems':
        if not isinstance(cyc, list) and cyc in _ALL:
            setattr(self, attr, None)
            return self

        if clear:
            setattr(self, attr, None)

        if getattr(self, attr) is None:
            setattr(self, attr, [])

        if isinstance(cyc, _INDEX) or isfunction(cyc):
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

    def keys(self, sel = None) -> 'Iterator':
        u"returns accepted keys"
        self._unlazyfy()
        if sel is None:
            sel = self.selected
        if self.discarded is None:
            yield from (key for key in self._keys(sel))
        else:
            disc = frozenset(self._keys(self.discarded))
            yield from (key for key in self._keys(sel) if key not in disc)

    def __iter__(self) -> 'Iterator[Tuple[Any, Sequence[float]]]':
        self._unlazyfy()
        act = self.getaction()
        if act is None:
            yield from (col      for col in self._iter())
        else:
            yield from (act(col) for col in self._iter())

    __NONE = type('__NONE', (), {})
    def get(self, key, default = __NONE):
        u"get an item"
        if default is not self.__NONE:
            vals = next(self._iter(sel = [key]))
        else:
            vals = next(self._iter(sel = [key]), default)
            if vals is default:
                return default

        act = self.getaction()
        if act is not None:
            return act(vals)[1]
        return vals[1]

    def __getitem__(self, keys):
        if isinstance(keys, slice):
            # could be a slice of beads or a slice of bead data ...
            raise NotImplementedError()

        elif (isinstance(keys, (str, int))
              or (isinstance(keys, tuple) and _ALL.isdisjoint(keys))):
            # this is NOT a slice
            return self.get(keys)

        else:
            # consider this a slice
            cpy = shallowcopy(self)
            return cpy.selecting(keys, clear = True)

    def _keys(self, sel:'Optional[Sequence]') -> 'Iterable':
        if sel is None:
            yield from (i for i in self.data.keys())
        else:
            keys = frozenset(self.data.keys())
            yield from (i for i in sel if i in keys)

    def _iter(self, sel = None) -> 'Iterator[Tuple[Any,Any]]':
        yield from ((bead, self.data[bead]) for bead in self.keys(sel))

class Beads(TrackItems, Items):
    u"""
    Class for iterating over beads:

    * providing all: selects all beads

    * providing names or ids: selects only those columns
    """
    level = Level.bead
    def _keys(self, sel):
        if sel is None:
            yield from self.data.keys()
        elif isinstance(self.data, Beads):
            yield from self.data.keys(sel)
        else:
            keys = frozenset(self.data.keys())
            yield from (i for i in sel if i in keys)

    def _iter(self, sel = None):
        if isinstance(self.data, Beads):
            if sel is None:
                yield from self.data
            else:
                yield from shallowcopy(self.data).selecting(sel)
            return

        yield from ((bead, self.data[bead]) for bead in self.keys(sel))

    def __getitem__(self, keys):
        if isinstance(keys, tuple):
            if len(keys) == 2:
                return Cycles(track = self.data, data = self)[keys]
            raise NotImplementedError()
        return super().__getitem__(keys)

    @staticmethod
    def _isbead(key):
        return isinstance(key, int)

class Cycles(TrackItems, Items):
    u"""
    Class for iterating selected cycles:

    * providing a pair (column name, cycle id) will extract a cycle on
      this column only.

    * providing a pair (column name, all) will extract all cycles for a given bead.

    * providing with a unique cycle id will extract all columns for that cycle
    """
    level = Level.cycle
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

    @staticmethod
    def _isbead(key):
        return isinstance(key, int)

    def _keys(self, sel) -> 'Iterable[Tuple[Union[str,int], int]]':
        if isinstance(self.data, Cycles):
            yield from self.data.keys(sel)
            return

        allcycles = range(self.track.ncycles)
        beads     = tuple(Beads(track = self.track, data = self.data).keys())
        if sel is None:
            yield from ((col, cid) for col in beads for cid in allcycles)
            return

        for thisid in sel:
            if isinstance(thisid, (tuple, list)):
                bid, tmp = thisid[0], thisid[1] # type: Union[str,int], Any
                if bid in _ALL and tmp in _ALL:
                    thisid = ...
                elif bid in _ALL:
                    thisid = tmp
                elif tmp in _ALL:
                    yield from ((bid, cid) for cid in allcycles)
                    continue
                else:
                    yield (bid, tmp)
                    continue

            if thisid in _ALL:
                yield from ((col, cid) for col in beads for cid in allcycles)

            else:
                yield from ((col, thisid) for col in beads)

    def _iter(self, sel = None):
        if isinstance(self.data, Cycles):
            if sel is None:
                yield from self.data
            else:
                yield from shallowcopy(self.data).selecting(sel)

        else:
            ncycles = self.track.ncycles
            nphases = self.track.nphases
            phaseid = self.track.phaseid

            first   = 0       if self.first is None else self.first
            last    = nphases if self.last  is None else self.last+1

            def _getdata(bid:int, cid:int):
                ind1 = phaseid(cid, first)
                if last == nphases:
                    if cid+1 >= ncycles:
                        return self.name(bid, cid), self.data[bid][ind1:]

                    ind2 = phaseid(cid+1, 0)
                else:
                    ind2 = phaseid(cid, last)

                return self.name(bid, cid), self.data[bid][ind1:ind2]

            yield from (_getdata(bid, cid) for bid, cid in self.keys(sel))

    def phaseid(self, cid:'Optional[int]' = None, pid:'Optional[int]' = None):
        u"returns phase ids for the given cycle"
        vect = self.track.phaseids
        if {cid, pid}.issubset(_ALL):
            return vect         - vect[:,0]
        elif cid in _ALL:
            return vect[:,pid]  - vect[:,0]
        elif pid in _ALL:
            return vect[cid,:]  - vect[cid,0]
        else:
            return vect[cid,pid]- vect[cid,0]

def createTrackItem(level:Optional[Level] = Level.none, **kwargs):
    u"Returns the item type associated to a level"
    subs = Items.__subclasses__()
    cls  = next(opt for opt in subs if level is opt.level)
    return cls(**kwargs)
