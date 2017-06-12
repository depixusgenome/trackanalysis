#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Selecting beads"

from    typing       import NamedTuple
import  numpy        as     np
from    utils        import initdefaults
from    signalfilter import nanhfsigma

RESULTS  = NamedTuple('Results', [('isvalid', bool), ('noisy', int), ('collapsed', int)])
class BeadSelection:
    "bead selection"
    minsigma = 1e-4
    maxsigma = 1e-2
    ncycles  = 50
    minsize  = .5

    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        pass

    def __call__(self, bead: np.array, starts:np.array, ends:np.array) -> RESULTS:
        "whether there are enough cycles"
        cycs       = np.array([bead[i:j] for i, j in zip(starts, ends)], dtype = 'O')

        sigmas     = np.array([nanhfsigma(i) for i in cycs])
        good       = self.minsigma < sigmas < self.maxsigma
        noisy      = len(good) - good.sum()

        good[good] = np.array([np.nanmax(i) - np.nanmin(i) for i in cycs[good]]) > self.minsize
        collapsed  = len(good) - noisy - good.sum()

        return RESULTS(good.sum() > self.ncycles, noisy, collapsed)
