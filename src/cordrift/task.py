#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Removing correlated drifts"

from typing                 import Union       # pylint: disable=unused-import
from model                  import Task, Level
from signalfilter.intervals import EventsDetector

class BeadDriftTask(Task):
    u"Removes correlations between cycles"
    level = Level.bead
    def __init__(self, **kwa):
        super().__init__(**kwa)
        self.filter        = None # Union[ForwardBackwardFilter,NonLinearFilter,type(None)]

        self.eventsfinder = kwa.get('eventsfinder', EventsDetector())
        self.precision    = kwa.get('precision',   0.)
        self.confidence   = kwa.get('confidence',  0.1)
        self.isequal      = kwa.get('isequal',     True)
        self.edgelength   = kwa.get('edgelength',  0)
        self.minlength    = kwa.get('minlength',   5)

