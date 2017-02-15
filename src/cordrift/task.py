#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=unused-import
u"Task for removing correlated drifts"

from typing         import Union, Optional, Tuple
from utils          import initdefaults
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
    @initdefaults('phases', 'collapse', 'stitch', 'zero', 'precision', 'onbeads')
    def __init__(self, **kwa):
        Task.__init__(self)
        EventDetectionConfig.__init__(self, **kwa)
