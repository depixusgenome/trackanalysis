#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Access to oligos and sequences"
from typing                 import Optional, Sequence
from control.modelaccess    import TaskPlotModelAccess
from model.globals          import ConfigRootProperty

class SequencePlotModelAccess(TaskPlotModelAccess):
    "access to the sequence path and the oligo"
    sequencepath = ConfigRootProperty[Optional[str]]          ('tasks.sequence.path')
    oligos       = ConfigRootProperty[Optional[Sequence[str]]]('tasks.oligos')

    def __init__(self, ctrl, key: str = None) -> None:
        super().__init__(ctrl, key)
        cls = type(self)
        cls.sequencepath.setdefault(self, None)
        cls.oligos      .setdefault(self, [], size = 4) # type: ignore
