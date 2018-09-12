#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Adds shortcuts for using Events
"""
from   typing                       import Tuple, Callable, FrozenSet, List, Union, cast
from   copy                         import copy as shallowcopy
from   functools                    import partial

import numpy                        as     np
import pandas                       as     pd

from   utils.decoration             import addto, addproperty, extend
from   control.processor.dataframe  import DataFrameProcessor
from   model.level                  import PHASE
from   model.__scripting__          import Tasks
from   data.track                   import Track, Axis
from   data.tracksdict              import TracksDict
from   data.views                   import Cycles
from   data.__scripting__.dataframe import adddataframe
from   ..processor                  import (ExtremumAlignmentTask,
                                            BiasRemovalTask,
                                            EventDetectionTask)
from   ..data                       import Events

_RETURN_TYPE = FrozenSet[Tuple[int, int]]
class Comparator:
    """
    This allows selecting cycles which accept provided conditions.

    The following will return a set of (bead, cycle) keys which follow the
    given condition. These keys can be provided in turn to a `Cycles` or an `Events`
    view to iterate over these keys only:

    ```python
    >> evts = Events(...)
    >> evts.any < 5         # keys such that any event's mean is lower than 5
    >> evts.all > 5         # keys such that all event means are greater than 5
    >> evts.median.all > 5  # keys such that all event *medians* are greater than 5
    >> evts[0].all > 5      # keys such that the first event's *mean* is greater than 5
    >> evts.any.start > 5   # keys such that there are events starting after 5 frames
    ```

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
        if name[0] == '_':
            return super().__getattribute__(name)

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
            fcn = (cast(Callable, np.nanmean) if key == 'data' else
                   cast(Callable, lambda i: i))
        else:
            fcn = cast(Callable, self.__func)

        ind  = self.__index
        evts = self.__events
        if np.isscalar(ind):
            return ((i, iter((fcn(j[key][ind]),)))  for i, j in evts if len(j) > ind)
        if ind not in (None, Ellipsis):
            return ((i, iter((fcn(j[key][ind]),)))  for i, j in evts  if len(j) > ind)
        return ((i, iter(fcn(k) for k in j[key])) for i, j in evts)

    def within(self, aother) -> _RETURN_TYPE:
        "Wether there are any/all events within a given range"
        if isinstance(aother, (slice, range)):
            other = aother.start, aother.stop # type: ignore
        else:
            other = tuple(aother)             # type: ignore
            if len(other) != 2:
                raise ValueError(f'Did not recognize {aother} as an interval')
        cond = self.__cond
        return frozenset(tuple(i for i, j in self.__vals()
                               if cond(other[0] < k < other[1] for k in j)))

    def count(self):
        "for filtering on the number of events in a cycle"
        self.__func = len
        return self

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

@extend(Events)
class _EventsMixin:
    """
    One can also select cycles which accept provided conditions.
    """
    __doc__ = __doc__ + '\n'.join(Comparator.__doc__.split('\n')[2:])

    def swap(self,
             data: Union[Track, TracksDict, Cycles, str, Axis] = None,
             axis: Union[str, Axis] = None) -> Events:
        "Returns indexes or values in data at the same key and index"
        this = cast(Events, self)
        if isinstance(data, TracksDict):
            if axis is not None:
                axis = Axis(axis)

            if this.track.key in data:
                data = cast(Track, data[this.track.key])
            elif axis is not None:
                data = cast(Track, data[Axis(axis).name[0]+this.track.key])
            else:
                raise KeyError("Unknown data")

        if isinstance(data, (str, Axis)):
            data = Track(path = this.track.path, axis = Axis(data))

        if isinstance(data, Track):
            data = data.cycles # type: ignore

        return this.withaction(partial(self._swap, cast(Cycles, data).withphases(PHASE.measure)))

    def index(self) -> Events:
        "Returns indexes at the same key and positions"
        return cast(Events, self).withaction(self._index)

    def concatenated(self):
        """
        Add a method that returns a cycle vector, with NaN values where no
        events is defined.
        """
        return cast(Events, self).withaction(self._concatenate)

    any  = property(lambda self: Comparator(self, any), doc = Comparator.__doc__)
    all  = property(lambda self: Comparator(self, all), doc = Comparator.__doc__)

    @staticmethod
    def _index(_, info):
        info[1]['data'] = [range(i,i+len(j)) for i, j in info[1]]
        return info

    @staticmethod
    def _swap(data, _, info):
        tmp             = data[info[0]]
        info[1]['data'] = [tmp[i:i+len(j)] for i, j in info[1]]
        return info

    @staticmethod
    def _concatenate(frame, info):
        size = frame.track.phase.duration(info[0][1], PHASE.measure)
        arr  = np.full(size, np.NaN, dtype = 'f4')
        for i, j in info[1]:
            arr[i:i+len(j)] = j
        return info[0], arr

adddataframe(Events)

@addto(Track, property)
def events(self) -> Events:
    "Returns events in phase 5 only"
    return self.apply(*Tasks.defaulttasklist(self, Tasks.eventdetection))
# pylint: disable=no-member
Track.events.__doc__ = Events.__doc__

@addproperty(TracksDict, 'events')
class EventTracksDict:
    "creates a dataframe for all keys"
    def __init__(self, track):
        self._items = track

    def dataframe(self, *tasks, **kwa):
        "creates a dataframe for all keys"
        return self._items.dataframe(Tasks.eventdetection, *tasks, **kwa)

__all__: List[str] = ['ExtremumAlignmentTask', 'BiasRemovalTask', 'EventDetectionTask']
