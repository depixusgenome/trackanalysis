#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Creates a projection histogram from available events"
import numpy as np
from ..projection       import BeadProjection
from .histogramfitter   import GroupByPeakAndBase

class ByProjection:
    """
    Finds peaks with a minimum *half*width and threshold
    """

    def __init__(self, **kwa):
        self.finder  : BeadProjection     = self.__attr("finder",  BeadProjection, kwa)
        self.grouper : GroupByPeakAndBase = self.__attr("grouper", GroupByPeakAndBase, kwa)

    def __call__(self, events, precision, pos, **_):
        data = [
            np.concatenate(i).astype('f4') if len(i) else np.empty(0, dtype = 'f4')
            for i in events
        ]
        ints = np.array([0]+[len(i) for i in data], dtype = 'i4').cumsum(dtype = 'i4')
        proj = self.finder.compute(precision, np.concatenate(data), ints[:-1], ints[1:])
        ids  = self.grouper(peaks     = proj.peaks,
                            elems     = pos,
                            precision = precision)
        return proj.peaks, ids

    @staticmethod
    def __attr(name, tpe, kwa):
        return (
            tpe()            if name not in kwa else
            tpe(**kwa[name]) if isinstance(kwa[name], dict) else
            kwa[name]
        )
