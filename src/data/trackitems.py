#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Adds easy access to cycles and events"
import  inspect
from    copy        import copy as shallowcopy
from    abc         import ABCMeta, abstractmethod
from    functools   import wraps
from    typing      import (Optional, Tuple, Union, # pylint: disable=unused-import
                            Any, List, Sequence, Iterable, Iterator,
                            TypeVar, Hashable, TYPE_CHECKING, Dict, cast)
import  numpy as np

from    utils       import isfunction, initdefaults
from    model       import Level

_m_ALL   = None, all, Ellipsis          # type: tuple
_m_INTS  = int, cast(type, np.integer)
_m_KEYS  = int, cast(type, np.integer), str
_m_INDEX = int, cast(type, np.integer), str, tuple
_m_NONE  = type('_m_NONE', (), {}) # pylint: disable=invalid-name

BEADKEY  = Union[str,int]
CYCLEKEY = Tuple[BEADKEY,int]
Self     = TypeVar('Self',  bound = '_m_ConfigMixin')
TSelf    = TypeVar('TSelf', bound = 'TrackItems')

def _m_setfield(fcn):
    "provides a setter return self"
    @wraps(fcn)
    def _wrap(self, item):
        name = fcn.__name__[len("with"):]
        setattr(self, name, item)
        return self
    return _wrap

def _m_selection(self:Self, attr, cyc, clear) -> Self:
    if not isinstance(cyc, List) and cyc in _m_ALL:
        setattr(self, attr, None)
        return self

    if clear:
        setattr(self, attr, None)

    if getattr(self, attr) is None:
        setattr(self, attr, [])

    if isinstance(cyc, _m_INDEX) or isfunction(cyc):
        getattr(self, attr).append(cyc)
    else:
        getattr(self, attr).extend(cyc)

    if len(getattr(self, attr)) == 0:
        setattr(self, attr, None)
    return self

def _m_unlazyfy(self:'TrackItems'):
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
        self.data = shallowcopy(self.track.data)

def _m_check_action_sig(fcn):
    sig = inspect.signature(fcn)
    try:
        sig.bind(1)
    except TypeError as exc:
        msg = 'Function should have a single positional argument'
        raise TypeError(msg) from exc

def _m_copy(item):
    "Copies the data"
    return item[0], np.copy(item[1])

ISelf = TypeVar('ISelf', bound = 'Items')
class Items(metaclass=ABCMeta):
    "Class for iterating over data"
    @abstractmethod
    def __getitem__(self:ISelf, val) -> Union[ISelf, np.ndarray]:
        "can return one item or a copy of self with only the selected keys"

    @abstractmethod
    def keys(self, _1 = None, _2 = None) -> Iterator:
        "iterates over keys"
        assert _1 is None # should not be necessary: dicts can't do that
        assert _2 is None # should not be necessary: dicts can't do that
        return iter(tuple())

class TransformedItems:
    "Dictionnary that will transform its data when a value is requested"
    __slots__ = ('_data', '_parent', '_fcn')
    def __init__(self, fcn, data, parent = None) -> None:
        super().__init__()
        self._data   = data
        self._parent = parent
        self._fcn    = fcn

    @property
    def track(self):
        "Returns the track if any"
        return getattr(self._data if self._parent is None else self._parent, 'track', None)

    def __getitem__(self, val):
        if self._fcn is not None:
            self._fcn(self._data, val)
            if self._parent is not None:
                self._parent.data = self._data
        return self._data[val]

    def keys(self, _1 = None, _2 = None) -> Iterator:
        "iterates over keys"
        assert _1 is None
        assert _2 is None
        yield from self._data.keys()

class _m_ConfigMixin: # pylint: disable=invalid-name
    data      = None    # type: Union[Items,TrackItems,TransformedItems,Dict,None]
    selected  = None    # type: Optional[List]
    discarded = None    # type: Optional[List]
    beadsonly = False
    actions   = []      # type: List
    parents   = tuple() # type: Union[Tuple,Hashable]
    _COPY     = None    # type: Optional[bool]
    def __init__(self, **kw) -> None:
        get = lambda x: kw.get(x, shallowcopy(getattr(self.__class__, x)))
        self.data      = get('data')
        self.parents   = get('parents')
        self.actions   = get('actions')
        self.beadsonly = get('beadsonly')

        _m_selection(self, 'selected',  get('selected'),  False)
        _m_selection(self, 'discarded', get('discarded'), False)

        if kw.get('copy', self._COPY):
            self.actions.append(getattr(self, 'copy', _m_copy))

        if kw.get('samples', None) is not None:
            samples = kw['samples']
            self.actions.append(lambda item: (item[0], item[1][samples]))

    copy = staticmethod(_m_copy)    # type: ignore

    @staticmethod
    def isbead(key) -> bool:
        "returns whether the key is one for a bead"
        return ((isinstance(key, tuple)
                 and len(key) > 0
                 and isinstance(key[0], _m_INTS)
                ) or isinstance(key,    _m_INTS))

    def withbeadsonly(self:Self, beadsonly = True) -> Self:
        "discards all but beads"
        self.beadsonly = beadsonly
        return self

    def withsamples(self:Self, samples) -> Self:
        "specifies that only some samples should be taken"
        if samples is not None:
            self.actions.append(lambda item: (item[0], item[1][samples]))
        return self

    def withcopy(self:Self, cpy:bool = True) -> Self:
        "specifies that a copy of the data should or shouldn't be made"
        fcn = getattr(self, 'copy', _m_copy)
        if cpy and fcn not in self.actions:
            self.actions.append(fcn)
        elif not cpy and fcn in self.actions:
            self.actions.remove(fcn)
        return self

    def withfunction(self:Self, fcn = None, clear = False, beadsonly = False) -> Self:
        "Adds an action with fcn taking a value as single argument"
        if clear:
            self.actions = []

        if fcn is None:
            return self

        _m_check_action_sig(fcn)
        if beadsonly:
            isbead = self.isbead
            @wraps(fcn)
            def _action(col):
                return col[0], (fcn(col[1]) if isbead(col[0]) else col[1])
            self.actions.append(_action)
        else:
            self.actions.append(lambda col: (col[0], fcn(col[1])))
        return self

    def withaction(self:Self, fcn = None, clear = False, beadsonly = False) -> Self:
        "Adds an action with fcn taking a (key, value) pair as single argument"
        if clear:
            self.actions = []

        if fcn is None:
            return self

        _m_check_action_sig(fcn)
        if beadsonly:
            isbead = self.isbead
            @wraps(fcn)
            def _action(col):
                return fcn(col) if isbead(col[0]) else col
            self.actions.append(_action)
        else:
            self.actions.append(fcn)
        return self

    def withdata(self:Self, dat, fcn = None, once = True) -> Self:
        "sets the data"
        if fcn is None and callable(dat) and not hasattr(dat, '__getitem__'):
            dat, fcn  = self.data, dat

        if fcn is None:
            self.data = dat
        else:
            self.data = TransformedItems(fcn, dat, self if once else None)
        return self

    def selecting(self:Self, cyc, clear = False) -> Self:
        "selects ids over which to iterate. See class doc."
        return _m_selection(self, 'selected', cyc, clear)

    def discarding(self:Self, cyc, clear = False) -> Self:
        "selects ids to discard. See class doc."
        return _m_selection(self, 'discarded', cyc, clear)

    def getaction(self, actions = None):
        "returns a function performing all actions"
        if actions is None:
            actions = self.actions
        if len(actions) > 1:
            def _act(item):
                for action in actions:
                    item = action(item)
                return item
            return _act
        elif len(actions) == 1:
            return actions[0]
        else:
            return None

class TrackItems(_m_ConfigMixin, Items):
    "Class for iterating over beads or creating a new list of data"
    level     = Level.none
    track     = None  # type: Any
    @initdefaults
    def __init__(self, **kw) -> None:
        super().__init__(**kw)

    def _keys(self, sel:Optional[Sequence], beadsonly: bool) -> Iterable:
        isbead = self.isbead
        if sel is None and beadsonly is False:
            yield from iter(self.data.keys())
        elif sel is None and beadsonly is True:
            yield from iter(i for i in self.data.keys() if isbead(i))
        else:
            keys = frozenset(self.data.keys())
            if beadsonly:
                yield from (i for i in sel if i in keys and isbead(i))
            else:
                yield from (i for i in sel if i in keys)

    def _iter(self, sel = None) -> Iterator[Tuple[Any,Any]]:
        if sel is None:
            sel = self.selected
        if sel is None and isinstance(self.data, dict):
            yield from self.data.items()   # pylint: disable=no-member
        else:
            yield from ((bead, self.data[bead]) for bead in self.keys(sel))

    def __copy__(self):
        other = type(self).__new__(type(self))
        other.__dict__.update(track = self.track,
                              **{i: shallowcopy(j)
                                 for i, j in self.__dict__.items() if i != 'track'})
        return other

    def __iter__(self) -> Iterator[Tuple[Any, np.ndarray]]:
        _m_unlazyfy(self)
        act = self.getaction()
        if act is None:
            yield from (col      for col in self._iter())
        else:
            yield from (act(col) for col in self._iter())

    def __getitem__(self:TSelf, keys) -> Union[TSelf, np.ndarray]:
        if isinstance(keys, slice):
            # could be a slice of beads or a slice of bead data ...
            raise NotImplementedError()

        elif (keys in _m_ALL
              or (isinstance(keys, tuple) and frozenset(keys).issubset(_m_ALL))):
            return shallowcopy(self)

        elif (isinstance(keys, _m_KEYS)
              or (isinstance(keys, tuple) and frozenset(_m_ALL).isdisjoint(keys))):
            # this is NOT a slice
            return self.get(keys)

        else:
            # consider this a slice
            cpy = shallowcopy(self)
            return cpy.selecting(keys, clear = True)

    def new(self:TSelf, tpe: Optional[type] = None, **kwa) -> TSelf:
        "returns a item containing self in the data field"
        kwa.setdefault('track', self.track)
        kwa.setdefault('data',  self)
        kwa.setdefault('cycles', getattr(self, 'cycles', None))
        return (type(self) if tpe is None else tpe)(**kwa)

    def keys(self,
             sel      :Optional[Sequence] = None,
             beadsonly:Optional[bool]     = None) -> Iterator:
        "returns accepted keys"
        _m_unlazyfy(self)
        if sel is None:
            sel = self.selected
        if beadsonly is None:
            beadsonly = self.beadsonly

        if self.discarded is None:
            yield from self._keys(sel, beadsonly)
        else:
            disc = frozenset(self._keys(self.discarded, None))
            yield from (key for key in self._keys(sel, beadsonly) if key not in disc)

    def values(self) -> Iterator[np.ndarray]:
        "returns the values only"
        yield from (i for _, i in self.__iter__())

    def get(self, key, default = _m_NONE):
        "get an item"
        if default is _m_NONE:
            vals = next(self._iter(sel = [key]))
        else:
            vals = next(self._iter(sel = [key]), default)
            if vals is default:
                return default

        act = self.getaction()
        if act is not None:
            return act(vals)[1]
        return vals[1]

class Beads(TrackItems, Items):
    """
    Class for iterating over beads:

    * providing all: selects all beads

    * providing names or ids: selects only those columns
    """
    level  = Level.bead
    cycles = None # type: Optional[slice]
    def __init__(self, **kwa):
        super().__init__(self, **kwa)
        self.withcycles(kwa.get('cycles', ...))

    def _keys(self, sel:Optional[Sequence], beadsonly: bool) -> Iterator[BEADKEY]:
        if (sel is not None or beadsonly) and isinstance(self.data, Beads):
            yield from iter(cast(Beads, self.data).keys(sel, beadsonly))
        else:
            yield from super()._keys(sel, beadsonly)

    def _iter(self, sel = None) -> Iterator[Tuple[BEADKEY, np.ndarray]]:
        if isinstance(self.data, Beads) and self.cycles is None:
            beads = cast(Beads, self.data)
            if sel is None:
                sel = self.selected

            if sel is None:
                yield from beads.__iter__() # pylint: disable=no-member
            else:
                yield from shallowcopy(beads).selecting(sel).__iter__()
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
                res = Cycles(track = self.track, data = self)
                if isinstance(self.cycles, slice):
                    if frozenset(keys).issubset(_m_ALL):
                        return res.selecting([(..., i) for i in self.cyclerange()])
                    elif keys[1] in _m_ALL:
                        return res.selecting([(keys[0], i) for i in self.cyclerange()])
                    elif keys[1] not in self.cyclerange():
                        return res.new(data = {}, direct = True)
                    else:
                        return res[keys]
                return res if frozenset(keys).issubset(_m_ALL) else res[keys]
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

    def withcycles(self, cyc:Optional[slice]) -> 'Beads':
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



    @staticmethod
    def isbead(key:BEADKEY) -> bool:
        "returns whether the key is one for a bead"
        return isinstance(key, _m_INTS)

    if TYPE_CHECKING:
        def keys(self,
                 sel      :Optional[Sequence] = None,
                 beadsonly:Optional[bool]     = None) -> Iterator[BEADKEY]:
            yield from super().keys(sel, beadsonly)

        def __iter__(self) -> Iterator[Tuple[BEADKEY, np.ndarray]]:
            yield from super().__iter__()

class Cycles(TrackItems, Items):
    """
    Class for iterating over selected cycles:

    * providing a pair (column name, cycle id) will extract a cycle on
      this column only.

    * providing a pair (column name, all) will extract all cycles for a given bead.

    * providing with a unique cycle id will extract all columns for that cycle
    """
    level  = Level.cycle
    first  = None   # type: Optional[int]
    last   = None   # type: Optional[int]
    direct = False  # type: bool

    @initdefaults
    def __init__(self, **kw):
        super().__init__(**kw)

    def __keysfrombeads(self, sel, beadsonly):
        beads     = tuple(Beads(track = self.track, data = self.data).keys(None, beadsonly))
        allcycles = range(self.track.ncycles)
        if sel is None:
            yield from ((col, cid) for col in beads for cid in allcycles)
            return

        isbead = Beads.isbead
        for thisid in sel:
            if isinstance(thisid, (tuple, list)):
                bid, tmp = thisid[0], thisid[1] # type: BEADKEY, Any
                if bid in _m_ALL and tmp in _m_ALL:
                    thisid = ...
                elif bid in _m_ALL:
                    thisid = tmp
                elif beadsonly and not isbead(bid):
                    continue
                elif tmp in _m_ALL:
                    yield from ((bid, cid) for cid in allcycles)
                    continue
                else:
                    yield (bid, tmp)
                    continue

            if thisid in _m_ALL:
                yield from ((col, cid) for col in beads for cid in allcycles)

            else:
                yield from ((col, thisid) for col in beads)

    def __keysdirect(self, sel):
        if sel is None:
            yield from self.data.keys()
            return

        for thisid in sel:
            if isinstance(thisid, (tuple, list)):
                bid, tmp = thisid[0], thisid[1] # type: BEADKEY, Any
                if bid in _m_ALL and tmp in _m_ALL:
                    thisid = ...
                elif bid in _m_ALL:
                    thisid = tmp
                elif tmp in _m_ALL:
                    yield from (i for i in self.data.keys() if i[0] == bid)
                    continue
                else:
                    yield (bid, tmp)
                    continue

            if thisid in _m_ALL:
                yield from self.data.keys()

            else:
                yield from (i for i in self.data.keys() if i[1] == thisid)

    def _keys(self, sel, beadsonly) -> Iterable[CYCLEKEY]:
        if isinstance(self.data, Cycles):
            yield from cast(Cycles, self.data).keys(sel, beadsonly)

        elif self.direct:
            if beadsonly:
                isbead = self.isbead
                yield from (i for i in self.__keysdirect(sel) if isbead(i))
            else:
                yield from self.__keysdirect(sel)
        else:
            yield from self.__keysfrombeads(sel, beadsonly)

    def __iterfrombeads(self, sel = None):
        ncycles = self.track.ncycles
        nphases = self.track.nphases
        phase   = self.track.phase

        first   = 0       if self.first is None else self.first
        last    = nphases if self.last  is None else self.last+1

        data    = {}
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
            else:
                yield from shallowcopy(cycles).selecting(sel).__iter__()

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

    @_m_setfield
    def withfirst(self, first:Optional[int]) -> 'Cycles':
        "specifies the phase to extract: None for all"

    @_m_setfield
    def withlast(self, last:Optional[int]) -> 'Cycles':
        "specifies the phase to extract: None for all"

    def phase(self, cid:Optional[int] = None, pid:Optional[int] = None):
        "returns phase ids for the given cycle"
        vect = self.track.phases
        if {cid, pid}.issubset(_m_ALL):
            return vect         - vect[:,0]
        elif cid in _m_ALL:
            return vect[:,pid]  - vect[:,0]
        elif pid in _m_ALL:
            return vect[cid,:]  - vect[cid,0]
        else:
            return vect[cid,pid]- vect[cid,0]

    def maxsize(self):
        "returns the max size of cycles"
        if isfunction(self.track):
            self.track = self.track()

        first = self.track.phase(..., 0 if self.first is None else self.first)
        if self.last is None or self.last == self.track.nphases-1:
            return np.max(np.diff(first))
        else:
            last = self.track.phase(..., self.last+1)
            return np.max(last - first)

    @staticmethod
    def isbead(key:CYCLEKEY) -> bool:
        "returns whether the key is one for a bead"
        return isinstance(key[0], _m_INTS)

    if TYPE_CHECKING:
        def __getitem__(self, keys) -> Union['Cycles',np.ndarray]:
            return super().__getitem__(keys)

        def keys(self,
                 sel      :Optional[Sequence] = None,
                 beadsonly:Optional[bool]     = None) -> Iterator[CYCLEKEY]:
            yield from super().keys(sel)


        def __iter__(self) -> Iterator[Tuple[CYCLEKEY, np.ndarray]]:
            yield from super().__iter__()

def createTrackItem(level:Optional[Level] = Level.none, **kwargs):
    "Returns the item type associated to a level"
    subs = Items.__subclasses__()
    cls  = next(opt for opt in subs if level is getattr(opt, 'level', '--NONE--'))
    return cls(**kwargs) # type: ignore
