#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Collapses intervals"
from typing import Optional
import numpy as np # type: ignore

class Profile:
    u"A bead profile"
    def __init__(self, inter):
        self.xmin  = min(i[0][0]   for i in inter)
        self.xmax  = max(i[0][-1]  for i in inter)+1
        length     = self.xmax-self.xmin
        self.count = np.zeros((length,), dtype = np.int32)
        self.value = np.zeros((length,), dtype = np.float32)

def _indexes(rng, xmin:Optional[int] = None, xmax:Optional[int] = None) -> np.ndarray:
    u'returns indexes linked to this range'
    if xmax is None:
        return rng[rng >= xmin] - xmin
    elif xmin is None:
        return rng[rng < xmax]
    else:
        return rng[rng >= xmin & rng < xmax] - xmin

def _occupation(inter, xmin:int, xmax:int) -> np.ndarray:
    u"returns the number of overlapping intervals in the [xmin, xmax] range"
    ret = np.zeros((xmax-xmin,), dtype = np.int32)
    for rng in inter:
        ret[_indexes(rng[0], xmin, xmax)] += 1
    return ret

def intervals(inter) -> Profile:
    u"Collapses intervals together using their mean values"
    inter = tuple(inter)
    prof  = Profile(inter)

    for rng in sorted(inter, key = lambda i: (-i[0][-1], len(i[0]))):
        inds = _indexes(rng[0], prof.xmin)
        if len(inds) == 0:
            continue

        cur               = rng[1][rng[0] >= prof.xmin]
        prof.value[inds] += (np.average(prof.value[inds], weights = prof.count[inds])
                             - cur.mean())
        prof.value[inds] += cur
        prof.count[inds] += 1

    return prof

class DerivateMode(Enum):
    median = 'median'
    mean   = 'mean'

def derivate(inter, maxder = np.inf, mode: DerivateMode = DerivateMode.median) -> Profile:
    u"""
    Collapses intervals together using the mean or median of their derivate
    at each point
    """
    assert mode in ('median', 'mean')

    inter = tuple(inter)
    prof  = Profile(inter)

    vals  = np.full((max(_occupation(inter, prof.xmin, prof.xmax)), len(inter)),
                    np.NaN, dtype = np.float32)
    occ   = np.zeros(vals.shape[0], dtype = np.int32)

    # compactify all derivatives into a single 2D table
    # missing values are coded as NaN
    for rng in inter:
        inds = _indexes(rng[0], prof.xmin)
        inds = inds[1:][np.diff(inds) == 1]

        vals[inds, max(occ[inds])] = np.diff(rng[1][rng[0] >= prof.xmin])
        occ[inds]                 += 1
    vals[vals > maxder] = np.NaN

    np.nansum(vals != np.NaN,     axis = 1, out = prof.count)
    getattr(np, 'nan'+mode.value)(vals, axis = 1, out = prof.value)

    good             = prof.value != np.NaN
    vgood            = prof.value[good][::-1]
    prof.value[good] = np.cumsum(vgood, out = vgood)[::-1]
    return prof
