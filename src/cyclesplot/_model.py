#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"access to the model"

from    typing                      import Optional, Sequence, Tuple
from    cordrift.processor          import DriftTask
from    eventdetection.processor    import (ExtremumAlignmentTask,
                                            EventDetectionTask)
from    view.plots.tasks            import TaskPlotModelAccess, TaskAccess
from    view.plots.sequence         import SequenceKeyProp, FitParamProp

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
        self.eventdetection = TaskAccess(self, EventDetectionTask)
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
