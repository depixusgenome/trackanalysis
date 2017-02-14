#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=unused-import
u"Task for removing correlated drifts"

from typing         import Union, Optional, Tuple
from model          import Task, Level
from eventdetection import EventDetectionConfig
from .collapse      import (CollapseAlg, StitchAlg,
                            CollapseByMerging, StitchByDerivate)

class BeadDriftTask(Task, EventDetectionConfig):
    u"Removes correlations between cycles"
    level     = Level.bead
    phases    = (5, 5)                  # type: Optional[Tuple[int,int]]
    collapse  = CollapseByMerging()     # type: Optional[CollapseAlg]
    stitch    = StitchByDerivate()      # type: Optional[StitchAlg]
    zero      = 10
    precision = 0.
    onbeads   = True
    def __init__(self, **kwa):
        Task.__init__(self)
        EventDetectionConfig.__init__(self, **kwa)
        get             = lambda x: kwa.get(x, getattr(self.__class__, x))
        self.phases     = get('phases')
        self.collapse   = get('collapse')
        self.stitch     = get('stitch')
        self.zero       = get('zero')
        self.precision  = get('precision')
        self.onbeads    = get('onbeads')
