#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=unused-import
u"Task for removing correlated drifts"

from typing                 import Union, Optional
from model                  import Task, Level
from signalfilter           import NonLinearFilter, ForwardBackwardFilter
from signalfilter.intervals import EventsDetector
from .collapse              import (CollapseByDerivate, CollapseToMean,
                                    StitchByInterpolation, StitchByDerivate)

class BeadDriftTask(Task):
    u"Removes correlations between cycles"
    level     = Level.cycle
    filter    = None # type: Optional[Union[ForwardBackwardFilter, NonLinearFilter]]
    events    = None # type: Optional[EventsDetector]
    collapse  = None # type: Optional[Union[CollapseToMean, CollapseByDerivate]]
    stitch    = None # type: Optional[Union[StitchByDerivate, StitchByInterpolation]]
    precision = property(lambda self: self._precision,
                         lambda self, val: self.setprecision(val))
    def __init__(self, **kwa):
        super().__init__(**kwa)
        self._precision = kwa.get('precision',  0.)
        self.phases     = kwa.get('phases',    (5, 5))
        self.filter     = kwa.get('filter',    NonLinearFilter())
        self.events     = kwa.get('intervals', EventsDetector())
        self.collapse   = kwa.get('collapse',  CollapseByDerivate())
        self.stitch     = kwa.get('stitch',    StitchByDerivate())
        self.zero       = kwa.get('zero',      10)
        self.setprecision(self._precision)

    def setprecision(self, val):
        u"sets the precision to all"
        self._precision = val
        for item in ('filter', 'events'):
            if getattr(self, item) is not None:
                setattr(self, item, val)
