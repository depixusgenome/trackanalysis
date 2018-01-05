#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Computes things for qc"
from    typing              import Tuple, List
import  numpy               as     np

from    data                import Cycles, Beads
from    cleaning.processor  import DataCleaningException

def extensions(beads: Beads, minphase: int, maxphase: int
              ) -> Tuple[List[np.ndarray], List[np.ndarray]]:
    """
    Computes the extension of each cycle for all beads.
    """
    cycles = Cycles(track = beads.track).withaction(lambda _, i: (i[0], np.nanmedian(i[1])))
    dtype  = np.dtype('i4, f4')

    cnt    = []
    cyc    = []
    ncyc   = beads.track.ncycles
    for ibead in beads.keys():
        try:
            data = beads[ibead]
        except DataCleaningException:
            continue

        ext = np.full(ncyc, np.NaN, dtype = 'f4')
        cnt.append(ext)
        cyc.append(np.arange(len(ext)))

        cycles.withdata({0: data}).withphases(minphase)
        tmp             = np.array([(i[1], j) for i, j in cycles], dtype = dtype)
        ext[tmp['f0']]  = tmp['f1']

        cycles.withphases(maxphase)
        tmp             = np.array([(i[1], j) for i, j in cycles], dtype = dtype)
        ext[tmp['f0']] -= tmp['f1']

        ext[:]         -= np.nanmedian(ext)

    return cyc, cnt
