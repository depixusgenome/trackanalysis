#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Tasks related to peakfinding"
from typing                         import Optional, Iterable
from functools                      import partial

from data.views                     import selectparent
from eventdetection.data            import Events, EventDetectionConfig
from taskcontrol.processor          import Processor
from taskmodel                      import Task, Level, PHASE
from utils                          import initdefaults
from ..probabilities                import Probability

class PeakProbabilityTask(Task):
    "Computes probabilities for each peak"
    level                        = Level.peak
    minduration: Optional[float] = None
    framerate:   Optional[float] = None
    @initdefaults(frozenset(locals()) - {'level'})
    def __init__(self, **kwa):
        super().__init__(**kwa)

class PeakProbabilityProcessor(Processor[PeakProbabilityTask]):
    "Computes probabilities for each peak"
    @staticmethod
    def _action(minduration, framerate, frame, info):
        rate = frame.track.framerate if framerate is None else framerate
        prob = Probability(minduration = minduration, framerate = rate)
        ends = frame.track.phase.duration(..., PHASE.measure)
        return info[0], iter((i[0], prob(i[1], ends)) for i in info[1])

    @classmethod
    def apply(cls, toframe = None, minduration = None, framerate = None, **_):
        "applies the task to a frame or returns a function that does so"
        if toframe is None:
            return cls.apply

        if minduration is None:
            tmp         = selectparent(toframe, Events)
            frame       = EventDetectionConfig() if tmp is None else tmp
            minduration = frame.events.select.minduration

        return toframe.withaction(partial(cls._action, minduration, framerate))

    @staticmethod
    def extractminduration(tasks: Iterable[Task]) -> Optional[float]:
        "get event min duration from tasks configuration"
        for i in tasks:
            if isinstance(i, EventDetectionConfig):
                return i.events.select.minduration

            proj = getattr(i, 'project', None)
            if hasattr(proj, 'countthreshold'):
                return proj.countthreshold
        return None

    def run(self, args):
        "updates frames"
        cnf = self.config()
        if cnf.get('minduration', None) is None:
            cnf['minduration'] = self.extractminduration(args.data.model)

        args.apply(partial(self.apply, **self.config()))
