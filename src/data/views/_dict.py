#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Adds easy access to cycles and events"
from    abc         import abstractmethod, abstractproperty
from    typing      import Tuple, Union, Iterator, TypeVar, cast, Dict, Optional
import  numpy as np
from    taskmodel   import Level

_m_ALL   = None, all, Ellipsis, slice(None) # type: tuple
_m_INTS  = int, cast(type, np.integer)
_m_KEYS  = int, cast(type, np.integer), str
_m_INDEX = int, cast(type, np.integer), str, tuple
_none    = type('_none', (), {})

def isint(vals):
    "checks whether the argument can be understood as an int"
    return isinstance(vals, _m_INTS)

def isellipsis(vals):
    "checks whether the argument can be understood as an ellipsis"
    return (not isinstance(vals, np.ndarray)) and vals in _m_ALL

CYCLEKEY = Tuple[int, int]
ISelf    = TypeVar('ISelf', bound = 'ITrackView')

class ITrackView:
    "Class for iterating over data"
    @property
    @abstractproperty
    def track(self):
        "returns the track"
        return None

    @abstractmethod
    def __getitem__(self:ISelf, val) -> Union[ISelf, np.ndarray]:
        "can return one item or a copy of self with only the selected keys"

    @abstractmethod
    def __iter__(self) -> Iterator:
        pass

    @abstractmethod
    def keys(self, _1 = None) -> Iterator:
        "iterates over keys"
        assert _1 is None # should not be necessary: dicts can't do that
        return iter(tuple())

class TransformedTrackView:
    "Dictionnary that will transform its data when a value is requested"
    __slots__ = ('_data', '_parent', '_fcn')
    def __init__(self, fcn, data, parent) -> None:
        super().__init__()
        self._data   = data
        self._parent = parent
        self._fcn    = fcn

    @property
    def track(self):
        "Returns the track if any"
        return getattr(self._data if self._parent is None else self._parent, 'track', None)

    def values(self):
        "Returns the values after running the computations"
        self.__run()
        yield from self._parent.data.values()

    def __getitem__(self, val):
        self.__run()
        return self._parent.data[val]

    def keys(self, _1 = None) -> Iterator:
        "iterates over keys"
        assert _1 is None
        yield from self._data.keys()

    def __run(self):
        fcn, self._fcn = self._fcn, None
        if fcn is not None:
            self._parent.data = fcn(self._data)

TrackViewType = Union[ITrackView, TransformedTrackView, Dict]

def createTrackView(level:Optional[Level] = Level.none, **kwargs):
    "Returns the item type associated to a level"
    subs = list(ITrackView.__subclasses__())
    while len(subs):
        cur = subs.pop()
        if (
                not getattr(cur, '__abstractmethods__', None)
                and level is getattr(cur, 'level', '?')
        ):
            return cur(**kwargs) # type: ignore
        subs.extend(cur.__subclasses__())
    raise TypeError(f"Could not find a subclass for level {level}")
