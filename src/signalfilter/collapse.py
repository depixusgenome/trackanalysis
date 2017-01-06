#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"""
Collapse intervals. The idea is to measure the behaviour common to all
stretches of data. This should be removed as it's source is either a (thermal,
electric, ...) drift or a mechanical vibration.
"""
from typing import Optional, Any # pylint: disable=unused-import
from enum   import Enum
import pandas
import numpy; np = numpy # type: Any # pylint: disable=multiple-statements,invalid-name

class Profile:
    u"A bead profile: the behaviour common to all stretches of data"
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
        return rng[np.logical_and(rng >= xmin, rng < xmax)] - xmin

def _occupation(inter, xmin:int, xmax:int) -> np.ndarray:
    u"returns the number of overlapping intervals in the [xmin, xmax] range"
    ret = np.zeros((xmax-xmin,), dtype = np.int32)
    for rng in inter:
        ret[_indexes(rng[0], xmin, xmax)] += 1
    return ret

def _iter_ranges(xmin, inter):
    for rng in inter:
        cur = rng[0] >= xmin
        if not any(cur):
            continue
        yield (rng[0][cur]-xmin, rng[1][cur])

def intervals(inter) -> Profile:
    u"Collapses intervals together using their mean values"
    inter = tuple(inter)
    prof  = Profile(inter)
    key   = lambda i: (-i[0][-1], len(i[0]))

    for inds, cur in _iter_ranges(prof.xmin, sorted(inter, key = key)):
        if all(prof.count[inds] == 0):
            prof.value[inds] -= cur.mean()
        else:
            prof.value[inds] += (np.average(prof.value[inds], weights = prof.count[inds])
                                 - cur.mean())
        prof.value[inds] += cur
        prof.count[inds] += 1

    prof.value[prof.count > 0] /= prof.count[prof.count > 0]
    return prof

class DerivateMode(Enum):
    u"Computation modes for the derivate method."
    median = 'median'
    mean   = 'mean'
    def __call__(self, vals, **kwa):
        return getattr(np, 'nan'+self.value)(vals, **kwa)

def derivate(inter, maxder = np.inf, mode: DerivateMode = DerivateMode.median) -> Profile:
    u"""
    Behaviour common to all is measured using the distribution of derivates at
    each time frame. Either the mean or the median is defined as the profile
    derivate.
    """
    inter = tuple(inter)
    prof  = Profile(inter)

    vals  = np.full((prof.xmax-prof.xmin, max(_occupation(inter, prof.xmin, prof.xmax))),
                    np.inf, dtype = np.float32)
    occ   = np.zeros(vals.shape[0], dtype = np.int32)

    # compactify all derivatives into a single 2D table
    # missing values are coded as NaN
    for inds, cur in _iter_ranges(prof.xmin, inter):
        sel  = np.where(np.diff(inds) == 1)
        inds = inds[sel]

        vals[inds, max(occ[inds])] = tuple(cur[i]-cur[i+1] for i in sel)
        occ[inds]                 += 1
    vals[vals >= maxder] = np.NaN

    np.sum(np.isfinite(vals), axis = 1, out = prof.count)

    vals[np.where(prof.count == 0), 0] = 0 # suppress all NaN warning
    prof.value = pandas.Series(mode(vals, axis = 1)[::-1]).cumsum().values[::-1]
    return prof
