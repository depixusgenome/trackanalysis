#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Tasks related to peakfinding"
from typing     import Optional # pylint: disable=unused-import

from model     import Task, Level
from .selector import PeakSelectorConfig

class PeakSelector(PeakSelectorConfig, Task):
    u"Groups events per peak"
    level = Level.event
    def __init__(self, **kwa):
        Task.__init__(self)
        PeakSelectorConfig.__init__(self, **kwa)
