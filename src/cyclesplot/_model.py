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
        super().__init__('sequence.key')

    def __get__(self, obj, tpe) -> Optional[str]:
        "returns the current sequence key"
        if obj is None:
            return self
        key  = super().__get__(obj, tpe)
        dseq = readsequence(obj.sequencepath)
        return next(iter(dseq), None) if key not in dseq else key

class FitParamProp(TaskPlotModelAccess.props.bead[float]):
    "access to bias or stretch"
    def __init__(self, attr):
        super().__init__('base.'+attr)
        self.__key = attr

    def __get__(self, obj, tpe) -> Optional[str]:
        val = super().__get__(obj, tpe)
        if val is None:
            return getattr(obj, 'estimated'+self.__key)
        return val

class CyclesModelAccess(TaskPlotModelAccess):
    "Model for Cycles View"
    def __init__(self, ctrl, key: Optional[str] = None) -> None:
        super().__init__(ctrl, key)
        cls = type(self)
        cls.oligos      .setdefault(self, [], size = 4)
        cls.binwidth    .setdefault(self, 0.003)
        cls.minframes   .setdefault(self, 10)
        cls.stretch     .setdefault(self, 8.8e-4)
        cls.bias        .setdefault(self, None)
        cls.peaks       .setdefault(self, None)
        cls.sequencekey .setdefault(self, None) # type: ignore

        self.alignment        = TaskAccess(self, ExtremumAlignmentTask)
        self.driftperbead     = TaskAccess(self, DriftTask, attrs = {'onbeads': True})
        self.driftpercycle    = TaskAccess(self, DriftTask, attrs = {'onbeads': False},
                                           side = 'RIGHT')
        self.eventdetection   = TaskAccess(self, EventDetectionTask)
        self.estimatedbias    = 0.
        self.estimatedstretch = 1.

    props        = TaskPlotModelAccess.props
    sequencekey  = SequenceKeyProp()
    sequencepath = props.configroot[Optional[str]]          ('last.path.sequence')
    oligos       = props.configroot[Optional[Sequence[str]]]('oligos')
    binwidth     = props.config[float]                      ('binwidth')
    minframes    = props.config[int]                        ('minframes')
    stretch      = props.bead[float]                        ('stretch')
    bias         = props.bead[float]                        ('bias')
    peaks        = props.bead[Optional[Tuple[float,float]]] ('sequence.peaks') # type: ignore
