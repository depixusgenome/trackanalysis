#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"access to the model"

from    typing                      import Optional, Sequence, Tuple, cast
from    cordrift.processor          import DriftTask
from    eventdetection.processor    import (ExtremumAlignmentTask,
                                            EventDetectionTask)
from    ..plotutils                 import PlotModelAccess, TaskAccess, readsequence

class CyclesModelAccess(PlotModelAccess):
    "Model for Cycles View"
    def __init__(self, ctrl, key: Optional[str] = None) -> None:
        order = tuple, ExtremumAlignmentTask, DriftTask, EventDetectionTask
        def _get(ttype, **kwa) -> TaskAccess:
            return TaskAccess(self, ttype, order, **kwa)
        self.alignment      = _get(ExtremumAlignmentTask)
        self.driftperbead   = _get(DriftTask, attrs = {'onbeads': True})
        self.driftpercycle  = _get(DriftTask, attrs = {'onbeads': False}, side = 'RIGHT')
        self.eventdetection = _get(EventDetectionTask)

        self.config.defaults = {'binwidth'          : .003,
                                'minframes'         : 10,
                                'base.bias'         : None,
                                'base.bias.step'    : .0001,
                                'base.bias.ratio'   : .25,
                                'base.stretch'      : 8.8e-4,
                                'base.stretch.start': 5.e-4,
                                'base.stretch.step' : 1.e-5,
                                'base.stretch.end'  : 1.5e-3,
                                'sequence.path' : None,
                                'sequence.key'  : None,
                               }
        self.config.sequence.peaks.default = None

        super().__init__(ctrl, key)

    props        = PlotModelAccess.props
    sequencepath = cast(Optional[str],           props.configroot('last.path.fasta'))
    oligos       = cast(Optional[Sequence[str]], props.configroot('oligos'))
    binwidth     = cast(float,                   props.config    ('binwidth'))
    minframes    = cast(int,                     props.config    ('minframes'))
    stretch      = cast(float,                   props.bead      ('base.stretch'))
    bias         = cast(Optional[float],         props.bead      ('base.bias'))
    peaks        = cast(Optional[Tuple[float,float,float,float]],
                        props.bead('sequence.peaks'))

    _sequencekey = cast(Optional[str],           props.bead      ('sequence.key'))
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
