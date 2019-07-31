#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Removing aberrant points and cycles"
from    importlib               import import_module
import  numpy                   as     np
from    taskmodel.base          import Rescaler
# pylint: disable=import-error
from    ._core                  import DataCleaning as _DataCleaning

# next lines are needed to open legacy .pk files...
locals().update({
    i for i in import_module("cleaning._core").__dict__.items()
    if i[0][0].upper() == i[0][0] and i[0][0] != '_'
})
locals()['DerivateIslands'] = locals().pop('NaNDerivateIslands')

class DataCleaning(Rescaler, _DataCleaning, zattributes = _DataCleaning.zscaledattributes()):
    "Remove specific points, cycles or even the whole bead."
    __doc__                = getattr(_DataCleaning, '__doc__', None)
    PRE_CORRECTION_CYCLES  = ('phasejump',)
    POST_CORRECTION_CYCLES = 'population', 'hfsigma', 'extent', 'pingpong'

    @staticmethod
    def badcycles(stats) -> np.ndarray:
        "returns all bad cycles"
        bad = np.empty(0, dtype = 'i4')
        if stats is None:
            return bad
        for stat in stats.values() if isinstance(stats, dict) else stats:
            bad = np.union1d(bad, stat.min)
            bad = np.union1d(bad, stat.max)
        return bad
