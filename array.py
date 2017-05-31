#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"utils for dealing with arrays"
from   typing import (Iterable, Optional, # pylint: disable=unused-import
                      Iterator, Sequence, Tuple, cast)
import numpy as np

EVENTS_TYPE  = Tuple[int, np.ndarray]
EVENTS_DTYPE = np.dtype([('start', 'i4'), ('data', 'O')])

def _m_asarray(arr:Iterable)-> np.array:
    tmp = None # type: Optional[Sequence]
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
    tmp = None # type: Optional[Sequence]
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

    return asview(vals, view, **kwa)

def asdataarrays(aevents:Iterable[Iterable], view: type = None, **kwa)-> Optional[np.ndarray]:
    "converts  an Iterable[Iterable] to a np.array"
    events = _m_asarray(aevents)
    first  = next((evt for evt in events if len(evt)), None)
    if first is None:
        return None

    if getattr(first, 'dtype', 'f') == EVENTS_DTYPE or not np.isscalar(first[0]):
        for j, evt in enumerate(events):
            events[j] = _m_asarray(evt)

    return asview(events, view, **kwa)

def asview(vals:np.ndarray, view:type, **kwa) -> np.ndarray:
    "converts to a given view"
    if view is None:
        return vals

    vals = vals.view(view)
    for i, j in kwa.items():
        setattr(vals, i, j)
    return vals
