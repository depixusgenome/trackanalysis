#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Tasks related to peakfinding"
from typing     import Optional # pylint: disable=unused-import

from model                      import Task, Level
from eventdetection.alignment   import CorrelationAlignment # pylint: disable=unused-import
from .finder                    import FindPeaks

class FindPeaksTask(FindPeaks, Task):
    u"Groups events per peak"
    level = Level.event
    def __init__(self, **kwa):
        Task.__init__(self)
        FindPeaks.__init__(self, **kwa)
