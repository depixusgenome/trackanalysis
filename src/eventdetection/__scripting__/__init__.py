#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Adds shortcuts for using Events
"""
import sys
from   typing           import Tuple, Callable, FrozenSet, Type
import numpy            as np
from   utils.decoration import addto
from   data             import Track
from   ..data           import Events

Tasks:           Type     = sys.modules['model.__scripting__'].Tasks
defaulttasklist: Callable = sys.modules['data.__scripting__'].defaulttasklist

@addto(Track) # type: ignore
@property
def events(self) -> Events:
    "returns events in phase 5 only"
    return self.apply(*defaulttasklist(self.path, Tasks.eventdetection))

_RETURN_TYPE = FrozenSet[Tuple[int, int]]
class Comparator:
    """
    Allows selecting event keys which accept provided conditions.

    Can be used as follows:

        >> evts = Events(...)
        >> evts.any < 5         # keys such that any event's mean is lower than 5
        >> evts.all > 5         # keys such that all event means are greater than 5
        >> evts.median.all > 5  # keys such that all event *medians* are greater than 5
        >> evts[0].all > 5      # keys such that the first event's *mean* is greater than 5
        >> evts.any.start > 5   # keys such that there are events starting after 5 frames

    In the 4th line, any numpy function name is accepted. The default is nanmean.

    In the 5th line, anything that can slice an np.array is accepted, although
    no care is taken about its validity unless a simple index is provided.
    """
    __slots__ = ('__events', '__func', '__index', '__cond', '__key')
    def __init__(self, evts, cond):
        self.__events: Events   = evts
        self.__index : int      = None
        self.__func  : Callable = None
        self.__cond  : Callable = cond
        self.__key   : str      = 'data'

    def __getitem__(self, ind):
        self.__index = ind
        return self

    def __getattr__(self, name):
        if name.lower() in ('data', 'start'):
            self.__key = name
        else:
            self.__func = name if callable(name) else getattr(np, name, None)
            if self.__func is None:
                raise AttributeError(f'{name} is neither a function nor a np method')
        return self

    def __vals(self):
        "selects cycles that have a condition"
        key  = self.__key
        if self.__func is None:
            fcn = np.nanmean if key == 'data' else lambda i: i
        else:
            fcn = self.__func

        ind  = self.__index
        evts = self.__events
        if np.isscalar(ind):
            return ((i, iter((fcn(j[key][ind]),)))  for i, j in evts if len(j) > ind)
        if ind not in (None, Ellipsis):
            return ((i, iter((fcn(j[key][ind]),)))  for i, j in evts)
        return ((i, iter(fcn(k) for k in j[key])) for i, j in evts if len(j) > ind)

    def __lt__(self, other) -> _RETURN_TYPE:
        cond = self.__cond
        return frozenset(tuple(i for i, j in self.__vals() if cond(k < other for k in j)))

    def __le__(self, other) -> _RETURN_TYPE:
        cond = self.__cond
        return frozenset(tuple(i for i, j in self.__vals() if cond(k <= other for k in j)))

    def __gt__(self, other) -> _RETURN_TYPE:
        cond = self.__cond
        return frozenset(tuple(i for i, j in self.__vals() if cond(k > other for k in j)))

    def __ge__(self, other) -> _RETURN_TYPE:
        cond = self.__cond
        return frozenset(tuple(i for i, j in self.__vals() if cond(k >= other for k in j)))

    def __eq__(self, other) -> _RETURN_TYPE: # type: ignore
        cond = self.__cond
        return frozenset(tuple(i for i, j in self.__vals() if cond(k == other for k in j)))

    def __ne__(self, other) -> _RETURN_TYPE: # type: ignore
        cond = self.__cond
        return frozenset(tuple(i for i, j in self.__vals() if cond(k != other for k in j)))

Events.any = property(lambda self: Comparator(self, any), doc = Comparator.__doc__)
Events.all = property(lambda self: Comparator(self, all), doc = Comparator.__doc__)
