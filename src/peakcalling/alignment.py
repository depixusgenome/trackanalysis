#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Aligns cycles using the hairpin theoretical peaks"
from  typing                import Union, Iterable

import numpy as np

from  peakfinding.alignment import (PeakCorrelationAlignment,
                                    PeakCorrelationAlignmentWorkTable,
                                    PeakCorrelationAlignmentAction)
from .tohairpin             import HairpinFitter


class HairpinCycleAlignment(PeakCorrelationAlignment, HairpinFitter):
    "Aligns each cycle to the sequence"
    class WorkTable(PeakCorrelationAlignmentWorkTable):
        "Contains data to be saved from action to action"
        def __init__(self, *args, **kwa):
            super().__init__(*args)
            self.stretch = kwa['stretch']
            self.bias    = kwa['bias']

    class Action(PeakCorrelationAlignmentAction):
        "Container class for computing a bias with given options."
        def reference(self, wtab, projector, hists):
            ref = wtab.parent.peaks/wtab.stretch + wtab.bias
            return projector.apply(*hists[1:], hists[0][0].shape[1], ref)

        @staticmethod
        def center(bias):
            return bias

    actions = [Action(subpixel = True)]

    def __init__(self, **kwa):
        PeakCorrelationAlignment.__init__(self, **kwa)
        HairpinFitter           .__init__(self, **kwa)

    def __call__(self,
                 data:      Union[np.ndarray, Iterable[np.ndarray]],
                 stretch:   float = 1.,
                 bias:      float = 0.,
                 precision: float = None,
                 **kwa) -> np.ndarray:
        return super().__call__(data,
                                stretch   = stretch,
                                bias      = bias,
                                precision = precision,
                                **kwa)
    def optimize(self, peaks: np.ndarray):
        "optimizes the cost function"
        raise AttributeError()
