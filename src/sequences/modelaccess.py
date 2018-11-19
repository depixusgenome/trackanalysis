#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Access to oligos and sequences"
from pathlib                import Path
from tempfile               import mkstemp
from typing                 import Any, Sequence, List, Optional, Dict, Union, cast

from utils                  import dataclass, field
from control.decentralized  import Indirection
from control.modelaccess    import TaskPlotModelAccess
from model.task.application import TasksDisplay
from .                      import (read as _readsequence, peaks as _sequencepeaks,
                                    splitoligos)

@dataclass
class SequenceConfig:
    "data for a DNA sequence"
    name     : str                             = "sequence"
    path     : Optional[str]                   = None
    sequences: Dict[str, str]                  = field(default_factory = dict)
    probes   : List[str]                       = field(default_factory = list)
    history  : List[Union[str, Sequence[str]]] = field(default_factory = list)
    maxlength: int                             = 10

@dataclass
class SequenceDisplay:
    """
    configuration for probrs
    """
    name  : str                              = "sequence"
    hpins : Dict[int, str]                   = field(default_factory = dict)
    probes: Dict[Any, Union[str, List[str]]] = field(default_factory = dict)

@dataclass
class SequenceModel:
    "everything sequence"
    config  : SequenceConfig  = field(default_factory = SequenceConfig)
    display : SequenceDisplay = field(default_factory = SequenceDisplay)
    tasks   : TasksDisplay    = field(default_factory = TasksDisplay)
    def addto(self, ctrl, noerase = False):
        "add to the controller"
        self.config  = ctrl.theme.  add(self.config,  noerase)
        self.display = ctrl.display.add(self.display, noerase)
        self.tasks   = ctrl.display.add(self.tasks,   noerase)
        return self

    def setnewkey(self, ctrl, new):
        "sets new probes"
        hpins = dict(self.display.hpins)
        if new is None:
            hpins.pop(self.tasks.bead, None)
        else:
            hpins[self.tasks.bead] = new
        ctrl.display.update(self.display, hpins = hpins)

    def setnewprobes(self, ctrl, new):
        "sets new probes"
        ols  = splitoligos(new)
        hist = self.config.history
        lst  = list(i for i in hist if i != ols)[:self.config.maxlength]
        ctrl.theme.update(self.config,  history = ([ols] if len(ols) else []) + lst)

        old  = dict(self.display.probes)
        if ols != old.get(self.tasks.roottask, None):
            old[self.tasks.roottask] = ols
            ctrl.display.update(self.display, probes = old)
        if ols != self.config.probes:
            ctrl.theme.update(self.config, probes = ols)

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
        return self.display.hpins.get(cast(int, self.tasks.bead), self._defaultkey)

    @property
    def currentprobes(self) -> Sequence[str]:
        "get current probe"
        return self.display.probes.get(self.tasks.roottask, self.config.probes)

class SequenceAnaIO:
    "stuff for loading/saving ana files"
    @staticmethod
    def onopenanafile(controller = None, model = None, **_):
        "action to be performed on opening a file"
        root = model.get('tasks', [[None]])[0][0]
        if root is None:
            return
        seq  = model.get('sequence', {})
        if 'path' in seq and not Path(seq['path']).exists():
            seq.pop("path")

        if 'sequences' in seq and 'path' not in seq:
            seq['path'] = mkstemp()[1]
            with open(seq['path'], "w") as stream:
                for i, j in seq['sequences'].items():
                    print(f"> {i}", file = stream)
                    print(j, file = stream)

        elif 'path' in seq and 'sequences' not in seq:
            try:
                seq['sequences'] = dict(_readsequence(seq['path']))
            except: # pylint: disable=bare-except
                seq.pop('path')

        if seq:
            def _fcn(model = None,  **_2):
                if model[0] is root:
                    controller.theme.update("sequence", **seq)
            controller.tasks.oneshot("opentrack", _fcn)

    @staticmethod
    def onsaveanafile(controller = None, model = None, **_):
        "action to be performed on saving a file"
        cnf = controller.theme.getconfig("sequence").maps[0]
        cnf.pop('history', None)
        cnf['probes'] = SequenceModel().addto(controller).currentprobes
        if not cnf['probes']:
            cnf.pop('probes')
        model["sequence"] = cnf

    @classmethod
    def observe(cls, controller):
        "observe io events"
        controller.display.observe("openanafile", cls.onopenanafile)
        controller.display.observe("saveanafile", cls.onsaveanafile)

class SequencePlotModelAccess(TaskPlotModelAccess):
    "access to the sequence path and the oligo"
    _seqconfig  = Indirection()
    _seqdisplay = Indirection()
    def __init__(self, ctrl) -> None:
        SequenceModel().addto(ctrl, noerase = False)
        super().__init__(ctrl)
        self._seqconfig  = SequenceConfig()
        self._seqdisplay = SequenceDisplay()

    @property
    def sequencemodel(self):
        "return the sequence model"
        return SequenceModel(self._seqconfig, self._seqdisplay, self._tasksdisplay)

    @property
    def sequencepath(self) -> Optional[str]:
        "return the seqence path"
        return self._seqconfig.path

    @property
    def sequencekey(self) -> Optional[str]:
        "returns the sequence key"
        return self.sequencemodel.currentkey

    @property
    def oligos(self) -> Optional[Sequence[str]]:
        "return the current probe"
        return self.sequencemodel.currentprobes

    def sequences(self, sequence = ...):
        "returns current sequences"
        seqs = self._seqconfig.sequences
        if sequence is Ellipsis:
            return dict(seqs)
        # pylint: disable=no-member
        return seqs.get(self.sequencekey if sequence is None else sequence, None)

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
        if not self.sequencemodel.setnewsequencepath(self._ctrl, path):
            self.reset()
            return False
        return True
