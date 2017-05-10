#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"access to the model"

from    typing                      import Optional, Sequence, Tuple

from    utils                       import NoArgs
from    cordrift.processor          import DriftTask
from    eventdetection.processor    import (ExtremumAlignmentTask,
                                            EventDetectionTask)
from    view.plots.tasks            import TaskPlotModelAccess, TaskAccess
from    view.plots.sequence         import SequenceKeyProp, FitParamProp

class EventDetectionTaskAccess(TaskAccess):
    "Access to the event detection task"
    def __init__(self, mdl):
        super().__init__(mdl, EventDetectionTask)
        self.config.eventdetection.isactive.default = False

    @property
    def task(self) -> Optional[EventDetectionTask]:
        "returns the task if it exists"
        if not self.config.eventdetection.isactive.get():
            return None
        return super().task

    def check(self, task, parent = NoArgs) -> bool:
        "wether this controller deals with this task"
        return (self.config.eventdetection.isactive.get()
                and super().check(task, parent))

    def remove(self):
        "removes the task"
        self.config.eventdetection.isactive.set(False)

    def update(self, **kwa):
        "adds/updates the task"
        self.config.eventdetection.isactive.set(not kwa.pop('disabled', False))
        super().update(**kwa)

class CyclesModelAccess(TaskPlotModelAccess):
    "Model for Cycles View"
    def __init__(self, ctrl, key: Optional[str] = None) -> None:
        super().__init__(ctrl, key)
        cls = type(self)
        cls.oligos      .setdefault(self, [], size = 4)
        cls.binwidth    .setdefault(self, 0.003)
        cls.minframes   .setdefault(self, 10)
        cls.stretch     .setdefault(self)
        cls.bias        .setdefault(self)
        cls.peaks       .setdefault(self, None)
        cls.sequencekey .setdefault(self, None) # type: ignore

        self.alignment      = TaskAccess(self, ExtremumAlignmentTask)
        self.driftperbead   = TaskAccess(self, DriftTask,
                                         attrs      = {'onbeads': True},
                                         configname = 'driftperbead')
        self.driftpercycle  = TaskAccess(self, DriftTask,
                                         attrs      = {'onbeads': False},
                                         configname = 'driftpercycle',
                                         side       = 'RIGHT')
        self.eventdetection = EventDetectionTaskAccess(self)
        self.estimatedbias  = 0.

    props        = TaskPlotModelAccess.props
    sequencekey  = SequenceKeyProp()
    sequencepath = props.configroot[Optional[str]]          ('last.path.sequence')
    oligos       = props.configroot[Optional[Sequence[str]]]('oligos')
    binwidth     = props.config[float]                      ('binwidth')
    minframes    = props.config[int]                        ('minframes')
    stretch      = FitParamProp                             ('stretch')
    bias         = FitParamProp                             ('bias')
    peaks        = props.bead[Optional[Tuple[float,float]]] ('sequence.peaks') # type: ignore
