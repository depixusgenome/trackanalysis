#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Access to oligos and sequences"
from typing                 import Any, Sequence, List, Optional, Dict, Union
from pathlib                import Path

from utils                  import initdefaults
from control.modelaccess    import TaskPlotModelAccess
from model.task.application import TasksDisplay
from .                      import (read as _readsequence, peaks as _sequencepeaks,
                                    splitoligos)

class SequenceConfig:
    "data for a DNA sequence"
    name                                       = "sequence"
    path: str                                  = None
    sequences: Dict[str, str]                  = {}
    history  : List[Union[str, Sequence[str]]] = []
    maxlength                                  = 10

    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        pass

class SequenceDisplay:
    """
    configuration for probrs
    """
    name                                     = "sequence"
    hpins:  Dict[int, str]                   = None
    probes: Dict[Any, Union[str, List[str]]] = {}

    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        pass

class SequenceModel:
    "everything sequence"
    config  = SequenceConfig()
    display = SequenceDisplay()
    tasks   = TasksDisplay()

    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        pass

    def setnewkey(self, ctrl, new):
        "sets new probes"
        if new == self.currentkey:
            return

        hpins = dict(self.display.hpins)
        hpins[self.tasks.bead] = new
        ctrl.theme.update(self.display, hpins = hpins)

    def setnewprobes(self, ctrl, new):
        "sets new probes"
        ols  = splitoligos(new)
        hist = self.config.history
        lst  = list(i for i in hist if i != ols)[:self.config.maxlength]
        ctrl.theme.update(self.config,  history = ([ols] if len(ols) else []) + lst)

        old  = dict(self.display.probes)
        if ols != old.get(self.tasks.roottask, None):
            old[self.tasks.roottask] = ols
            ctrl.display.update(self.display, probes = ols)

    def setnewsequencepath(self, ctrl, path) -> bool:
        "sets a new path if it is correct"
        if path is None or not Path(path).exists():
            return True
        try:
            seqs = dict(_readsequence(path))
        except: # pylint: disable=bare-except
            return True

        if len(seqs) > 0:
            ctrl.theme.update(self.config, path = path, sequences = seqs)
            ctrl.display.update(self.display, hpins = {})
            return False
        return True

    @property
    def _defaultkey(self):
        return next(iter(self.config.sequences.keys()), None)

    @property
    def currentkey(self) -> Optional[str]:
        "get current sequence key"
        return self.display.hpins.get(self.tasks.bead, self._defaultkey)

    @property
    def currentprobes(self) -> Optional[Sequence[str]]:
        "get current probe"
        return self.display.probes.get(self.tasks.roottask, None)

    @classmethod
    def create(cls, ctrl) -> 'SequenceDisplay':
        "create a new object from existing ones"
        self = cls()
        self.config  = ctrl.theme.  add(self.config,  True)
        self.display = ctrl.display.add(self.display, True)
        self.tasks   = ctrl.display.add(self.tasks,   True)
        return self

class SequencePlotModelAccess(TaskPlotModelAccess):
    "access to the sequence path and the oligo"
    def __init__(self, ctrl, key: str = None) -> None:
        super().__init__(ctrl, key)
        self.__seq = SequenceModel.create(ctrl)

    @property
    def sequencemodel(self):
        "return the sequence model"
        return self.__seq

    @property
    def sequencepath(self) -> Optional[str]:
        "return the seqence path"
        return self.__seq.config.path

    @property
    def sequencekey(self) -> Optional[str]:
        "returns the sequence key"
        return self.__seq.currentkey

    @property
    def oligos(self) -> Optional[Sequence[str]]:
        "return the current probe"
        return self.__seq.currentprobes

    def sequences(self, sequence = ...):
        "returns current sequences"
        seqs = self.__seq.config.sequences
        if sequence is Ellipsis:
            return dict(seqs)
        return seqs.get(self.__seq.currentkey if sequence is None else sequence, None)

    def hybridisations(self, sequence = ...):
        "returns the peaks"
        seqs = self.sequences(...)
        if len(seqs) != 0:
            ols = self.oligos
            if ols is not None and len(ols):
                if sequence is Ellipsis:
                    return {i: _sequencepeaks(j, ols) for i, j in seqs.items()}

                key = sequence if sequence is not None else self.sequencekey
                return None if key is None else _sequencepeaks(seqs[key], ols)
        return {} if sequence is Ellipsis else None

    def setnewsequencepath(self, path):
        "sets a new path if it is correct"
        return self.__seq.setnewsequencepath(self._ctrl, path)
