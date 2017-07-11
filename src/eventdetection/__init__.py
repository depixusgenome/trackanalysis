#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Deals with event detection"
from utils          import initdefaults
from signalfilter   import Filter, PrecisionAlg
from .detection     import EventDetector

class EventDetectionConfig(PrecisionAlg):
    u"Config for an event detection: base class to various interfaces"
    filter: Filter = None
    events         = EventDetector()
    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        super().__init__(**_)
