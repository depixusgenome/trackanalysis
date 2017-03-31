#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"access to the model"

from    typing                      import Optional, Sequence, Tuple
from    cordrift.processor          import DriftTask
from    eventdetection.processor    import (ExtremumAlignmentTask,
                                            EventDetectionTask)
from    view.plots.tasks            import TaskPlotModelAccess, TaskAccess
from    view.plots.sequence         import readsequence

class SequenceKeyProp(TaskPlotModelAccess.props.bead[Optional[str]]):
    "access to the sequence key"
    def __init__(self):
        super().__init__('sequence.peaks')

    def __get__(self, obj, val:Optional[str]) -> Optional[str]:
        "returns the current sequence key"
        if obj is None:
            return self
        key  = super().__get__(obj, val)
        dseq = readsequence(obj.sequencepath)
        return next(iter(dseq), None) if key not in dseq else key

class CyclesModelAccess(TaskPlotModelAccess):
    "Model for Cycles View"
    def __init__(self, ctrl, key: Optional[str] = None) -> None:
        super().__init__(ctrl, key)
        cls = type(self)
        cls.oligos      .setdefault(self, tuple(), size = 4)
        cls.binwidth    .setdefault(self, 0.003)
        cls.minframes   .setdefault(self, 10)
        cls.stretch     .setdefault(self, 8.8e-4,
                                    start = 5.e-4,
                                    step  = 1.e-5,
                                    end   = 1.5e-3)
        cls.bias        .setdefault(self, None, step = .0001, ratio = .25)
        cls.peaks       .setdefault(self, None)
        cls.sequencekey .setdefault(self, None) # type: ignore

        self.alignment      = TaskAccess(self, ExtremumAlignmentTask)
        self.driftperbead   = TaskAccess(self, DriftTask, attrs = {'onbeads': True})
        self.driftpercycle  = TaskAccess(self, DriftTask, attrs = {'onbeads': False},
                                         side = 'RIGHT')
        self.eventdetection = TaskAccess(self, EventDetectionTask)

    props        = TaskPlotModelAccess.props
    sequencekey  = SequenceKeyProp()
    sequencepath = props.configroot[Optional[str]]          ('last.path.fasta')
    oligos       = props.configroot[Optional[Sequence[str]]]('oligos')
    binwidth     = props.config[float]                      ('binwidth')
    minframes    = props.config[int]                        ('minframes')
    stretch      = props.bead[float]                        ('base.stretch')
    bias         = props.bead[Optional[float]]              ('base.bias')
    peaks        = props.bead[Optional[Tuple[float,float]]] ('sequence.peaks') # type: ignore
