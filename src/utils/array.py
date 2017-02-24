#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"utils"
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

def asobjarray(arr:Iterable)->np.ndarray:
    u"converts  an Iterable to a np.array"
    tmp = None # type: Optional[Sequence]
    if isinstance(arr, Iterator):
        tmp = tuple(arr)

    elif getattr(arr, 'dtype', '') != 'O':
        tmp = cast(Sequence, arr)

    elif getattr(arr, 'dtype', '') == 'O' and len(getattr(arr, 'shape', '')) > 1:
        tmp = tuple(arr)

    if tmp is None:
        return arr

    vals    = np.empty((len(tmp),), dtype = 'O')
    vals[:] = tmp
    return vals

def asdataarrays(aevents:Iterable[Iterable])->np.ndarray:
    u"converts  an Iterable[Iterable] to a np.array"
    events = _m_asarray(aevents)
    if len(events) == 0:
        return

    if getattr(events[0], 'dtype', 'f') == EVENTS_DTYPE or not np.isscalar(events[0][0]):
        for i, evt in enumerate(events):
            events[i] = _m_asarray(evt)

    if not any(len(i) for i in events):
        return None
    return events
