#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Deals with event detection"
from typing         import Optional
from signalfilter   import NonLinearFilter, Filter
from .detection     import EventDetector

class EventDetectionConfig:
    u"Config for an event detection: base class to various interfaces"
    filter      = NonLinearFilter() # type: Optional[Filter]
    events      = EventDetector()   # type: EventDetector
    precision   = 0.                # type: Optional[float]
    def __init__(self, **kw) -> None:
        get            = lambda x: kw.get(x, getattr(self.__class__, x))
        self.filter    = get('filter')
        self.events    = get('events')
        self.precision = get('precision')
