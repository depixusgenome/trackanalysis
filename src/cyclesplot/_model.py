#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"access to the model"

from    typing                      import Optional, Sequence, Tuple
from    cordrift.processor          import DriftTask
from    eventdetection.processor    import (ExtremumAlignmentTask,
                                            EventDetectionTask)
from    view.plots.tasks            import TaskPlotModelAccess, TaskAccess
from    view.plots.sequence         import readsequence

class CyclesModelAccess(TaskPlotModelAccess):
    "Model for Cycles View"
    def __init__(self, ctrl, key: Optional[str] = None) -> None:
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
        cls._sequencekey.setdefault(self, None) # pylint: disable=protected-access

        super().__init__(ctrl, key)
        self.alignment      = TaskAccess(self, ExtremumAlignmentTask)
        self.driftperbead   = TaskAccess(self, DriftTask, attrs = {'onbeads': True})
        self.driftpercycle  = TaskAccess(self, DriftTask, attrs = {'onbeads': False},
                                         side = 'RIGHT')
        self.eventdetection = TaskAccess(self, EventDetectionTask)



    props        = TaskPlotModelAccess.props
    sequencepath = props.configroot[Optional[str]]          ('last.path.fasta')
    oligos       = props.configroot[Optional[Sequence[str]]]('oligos')
    binwidth     = props.config[float]                      ('binwidth')
    minframes    = props.config[int]                        ('minframes')
    stretch      = props.bead[float]                        ('base.stretch')
    bias         = props.bead[Optional[float]]              ('base.bias')
    peaks        = props.bead[Optional[Tuple[float,float]]] ('sequence.peaks') # type: ignore
    _sequencekey = props.bead[Optional[str]]                ('sequence.key')

    @property
    def sequencekey(self) -> Optional[str]:
        "returns the current sequence key"
        key  = self._sequencekey
        dseq = readsequence(self.sequencepath)
        return next(iter(dseq), None) if key not in dseq else key

    @sequencekey.setter
    def sequencekey(self, value) -> Optional[str]:
        self._sequencekey = value
        return self._sequencekey
