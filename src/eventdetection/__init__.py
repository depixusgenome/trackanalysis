#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Deals with event detection"
from utils          import initdefaults
from signalfilter   import Filter, PrecisionAlg
from .detection     import EventDetector
from ._core         import samples # pylint: disable=import-error

class EventDetectionConfig(PrecisionAlg):
    """
    Find events in `PHASE.measure`

    # Attributes

    * `filter`: a signal processing filter applied to the data prior to
    dectecting events.
    * `events`: the algorithm used for detecting events
    """

    filter: Filter = None
    events         = EventDetector()
    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        super().__init__(**_)

    if __doc__:
        __doc__ +=  type(events).__doc__[type(events).__doc__.find("#")-5:] # type: ignore
