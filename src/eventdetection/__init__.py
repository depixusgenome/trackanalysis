#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Deals with event detection"
from typing         import Optional
from utils          import initdefaults
from signalfilter   import NonLinearFilter, Filter, PrecisionAlg
from .detection     import EventDetector

class EventDetectionConfig(PrecisionAlg):
    u"Config for an event detection: base class to various interfaces"
    filter      = NonLinearFilter() # type: Optional[Filter]
    events      = EventDetector()   # type: EventDetector
    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        super().__init__(**_)
