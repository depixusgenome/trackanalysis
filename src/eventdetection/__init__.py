#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Deals with event detection"
from typing         import Optional
from utils          import initdefaults
from signalfilter   import NonLinearFilter, Filter
from .detection     import EventDetector

class EventDetectionConfig:
    u"Config for an event detection: base class to various interfaces"
    filter      = NonLinearFilter() # type: Optional[Filter]
    events      = EventDetector()   # type: EventDetector
    precision   = 0.                # type: Optional[float]
    @initdefaults('filter', 'events', 'precision')
    def __init__(self, **_):
        pass
