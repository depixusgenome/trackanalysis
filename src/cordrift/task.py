#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=unused-import
u"Task for removing correlated drifts"

from typing               import Union, Optional
from model                import Task, Level
from signalfilter         import NonLinearFilter, Filter
from signalfilter.events  import EventDetector
from .collapse            import (CollapseAlg, StitchAlg,
                                  CollapseToMean, StitchByDerivate)

class BeadDriftTask(Task): # pylint: disable=too-many-instance-attributes
    u"Removes correlations between cycles"
    level     = Level.cycle
    filter    = None # type: Optional[Filter]
    events    = None # type: Optional[EventDetector]
    collapse  = None # type: Optional[CollapseAlg]
    stitch    = None # type: Optional[StitchAlg]
    def __init__(self, **kwa):
        super().__init__(**kwa)
        self.phases     = kwa.get('phases',    (5, 5))
        self.filter     = kwa.get('filter',    NonLinearFilter())
        self.filtered   = kwa.get('filtered',  ('events',))
        self.events     = kwa.get('intervals', EventDetector())
        self.collapse   = kwa.get('collapse',  CollapseToMean())
        self.stitch     = kwa.get('stitch',    StitchByDerivate())
        self.zero       = kwa.get('zero',      10)
        self.precision  = kwa.get('precision',  0.)
