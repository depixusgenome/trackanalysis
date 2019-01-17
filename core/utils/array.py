#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"utils for dealing with arrays"
from   typing import Iterable, Optional, Iterator, Union, Sequence, Tuple, cast
import numpy as np

EVENTS_TYPE  = Tuple[int, np.ndarray]                     # pylint: disable=invalid-name
EVENTS_DTYPE = np.dtype([('start', 'i4'), ('data', 'O')]) # pylint: disable=invalid-name

class EventsArray(np.ndarray):
    """
    Array with the following fields:

    * *discarded*: the number of discarded cycles
    """
    # pylint: disable=unused-argument
    discarded:  int
    _discarded: Union[int,bool] = False
    _dtype                      = EVENTS_DTYPE
    _order                      = None
    def __new__(cls, array, **kwa):
        obj  = np.asarray(array,
                          dtype = kwa.get('dtype', cls._dtype),
                          order = kwa.get('order', cls._order)
                         ).view(cls)
        obj.discarded = kwa.get('discarded', cls._discarded)
        return obj

    def __array_finalize__(self, obj):
        if obj is None:
            return
        self.discarded = getattr(obj, 'discarded', False)

    def __reduce_ex__(self, arg):
        fcn, red, state = super().__reduce_ex__(arg)
        return fcn, red, (state, self.discarded)

    def __setstate__(self, vals):
        super().__setstate__(vals[0])
        self.discarded = vals[1]

def _m_asarray(arr:Iterable)-> np.array:
    tmp: Optional[Sequence] = None
    if isinstance(arr, Iterator):
        tmp = tuple(arr)

    elif getattr(arr, 'dtype', 'f') == EVENTS_DTYPE:
        tmp = tuple(cast(np.ndarray, arr)['data'])

    elif getattr(arr, 'dtype', '') != 'O':
        tmp = cast(Sequence, arr)

    elif getattr(arr, 'dtype', '') == 'O' and len(getattr(arr, 'shape', '')) > 1:
        tmp = tuple(arr)

    if tmp is None:
        return arr

    vals    = np.empty((len(tmp),), dtype = 'O')
    vals[:] = tmp
    return vals

def asobjarray(arr:Iterable, view: type = None, **kwa)->np.ndarray:
    "converts  an Iterable to a np.array"
    tmp: Optional[Sequence] = None
    if isinstance(arr, Iterator):
        tmp = tuple(arr)

    elif getattr(arr, 'dtype', '') != 'O':
        tmp = cast(Sequence, arr)

    elif getattr(arr, 'dtype', '') == 'O' and len(getattr(arr, 'shape', '')) > 1:
        tmp = tuple(arr)

    if tmp is None:
        vals    = cast(np.ndarray, arr)
    else:

        vals    = np.empty((len(tmp),), dtype = 'O')
        vals[:] = tmp

    return asview(vals, view, **kwa) # type: ignore

def asdataarrays(aevents:Iterable[Iterable], view: type = None, **kwa)-> Optional[np.ndarray]:
    "converts  an Iterable[Iterable] to a np.array"
    events = _m_asarray(aevents)
    first  = next((evt for evt in events if len(evt)), None)
    if first is not None:
        if getattr(first, 'dtype', 'f') == EVENTS_DTYPE or not np.isscalar(first[0]):
            for j, evt in enumerate(events):
                events[j] = _m_asarray(evt)

    return asview(events, view, **kwa) # type: ignore

def asview(vals:np.ndarray, view:type, **kwa) -> np.ndarray:
    "converts to a given view"
    if view is None:
        return vals

    vals = vals.view(view)
    for i, j in kwa.items():
        setattr(vals, i, j)
    return vals

def repeat(data, count, axis = 1):
    """
    Repeats values along an axis.

        >>> assert repeat(np.arange(3), 2, axis == 1).reshape(3,2) == [[0,0], [1,1], [2,2]]
        >>> assert repeat(np.arange(3), 2, axis == 0).reshape(2,3) == [[0,1,2], [0,1,2]]
    """
    if axis == 1:
        return np.repeat(data, count)
    return np.repeat(np.asarray(data)[np.newaxis], count, axis = 0).ravel()
