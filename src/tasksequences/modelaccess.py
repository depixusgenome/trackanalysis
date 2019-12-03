#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Access to oligos and sequences"
from pathlib                 import Path
from tempfile                import mkstemp
from typing                  import Sequence, List, Optional, Dict, Union, cast

from taskcontrol.modelaccess import TaskPlotModelAccess
from taskmodel               import RootTask
from taskmodel.application   import TasksDisplay
from utils                   import dataclass, field
from .                       import (read as _readsequence, peaks as _sequencepeaks,
                                     splitoligos)

@dataclass
class SequenceConfig:
    "data for a DNA sequence"
    name:      str                             = "sequence"
    path:      Optional[str]                   = None
    sequences: Dict[str, str]                  = field(default_factory = dict)
    probes:    List[str]                       = field(default_factory = list)
    history:   List[Union[str, Sequence[str]]] = field(default_factory = list)
    maxlength: int                             = 10

@dataclass
class SequenceDisplay:
    """
    configuration for probes
    """
    name:      str                                   = "sequence"
    hpins:     Dict[int, str]                        = field(default_factory = dict)
    probes:    Dict[RootTask, Union[str, List[str]]] = field(default_factory = dict)
    paths:     Dict[RootTask, str]                   = field(default_factory = dict)
    sequences: Dict[RootTask, Dict[str, str]]        = field(default_factory = dict)

    def observe(self, ctrl):
        "observe the controller"
        @ctrl.tasks.observe
        @ctrl.display.hashwith(id(self))
        def _onopeningtracks(models, calllater, **_):
            "action to be performed on opening a file"

            @calllater.append
            def _call():
                mdl   = {i: dict(getattr(self, i)) for i in ('sequences', 'probes', 'paths')}
                lens  = {i: len(j) for i, j in mdl.items()}

                for _, proc in models:
                    root = proc.model[0]
                    if root in mdl['sequences']:
                        continue

                    task = next((i for i in proc.model if hasattr(i, 'sequences')), None)
                    if task is None:
                        continue

                    if task.oligos and task.oligos not in ('kmer', '3mer', '4mer'):
                        mdl['probes'][root] = (
                            [task.oligos] if isinstance(task.oligos, str) else task.oligos
                        )

                    if isinstance(task.sequences, dict):
                        mdl['sequences'][root] = task.sequences
                        mdl['paths'][root]     = mkstemp(
                            ".fasta", __name__.replace(".","_")+"_"
                        )[1]

                        with open(mdl['paths'][root], "w") as stream:
                            for i, j in mdl['sequences'][root].items():
                                print(f"> {i}", file = stream)
                                print(j, file = stream)

                    elif (
                            isinstance(task.sequences, (Path, str))
                            and Path(task.sequences).exists()
                    ):
                        out = dict(_readsequence(task.sequences))
                        if out:
                            mdl['paths'][root]     = task.sequences
                            mdl['sequences'][root] = out

                info = {i: j for i, j in mdl.items() if len(j) > lens[i]}
                if info:
                    ctrl.display.update(self, **info)

@dataclass
class SequenceModel:
    "everything sequence"
    config:  SequenceConfig  = field(default_factory = SequenceConfig)
    display: SequenceDisplay = field(default_factory = SequenceDisplay)
    tasks:   TasksDisplay    = field(default_factory = TasksDisplay)

    def swapmodels(self, ctrl):
        "add to the controller"
        self.config  = ctrl.theme.  swapmodels(self.config)
        self.display = ctrl.display.swapmodels(self.display)
        self.tasks   = ctrl.display.swapmodels(self.tasks)

    @property
    def _defaultkey(self):
        return next(iter(self.currentsequences.keys()), None)

    @property
    def currentsequences(self) -> Dict[str, str]:
        "get current sequences"
        return self.display.sequences.get(self.tasks.roottask, self.config.sequences)

    @property
    def currentpath(self) -> Optional[str]:
        "get current sequence key"
        return self.display.paths.get(self.tasks.roottask, self.config.path)

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
    def onsaveanafile(controller = None, model = None, **_):
        "action to be performed on saving a file"
        cnf = controller.theme.getconfig("sequence").maps[0]
        cnf.pop('history', None)

        mdl = SequenceModel()
        mdl.swapmodels(controller)
        cnf['probes'] = mdl.currentprobes
        if not cnf['probes']:
            cnf.pop('probes')
        model["sequence"] = cnf

    @classmethod
    def observe(cls, controller):
        "observe io events"
        controller.display.observe("saveanafile", cls.onsaveanafile)

class SequencePlotModelAccess(TaskPlotModelAccess):
    "access to the sequence path and the oligo"
    def __init__(self):
        super().__init__()
        self._seqconfig:  SequenceConfig  = SequenceConfig()
        self._seqdisplay: SequenceDisplay = SequenceDisplay()

    def swapmodels(self, ctrl) -> bool:
        "swap models with those in the controller"
        if super().swapmodels(ctrl):
            self._seqconfig  = ctrl.theme.swapmodels(self._seqconfig)
            self._seqdisplay = ctrl.display.swapmodels(self._seqdisplay)
            return True
        return False

    @property
    def sequencemodel(self):
        "return the sequence model"
        return SequenceModel(self._seqconfig, self._seqdisplay, self._tasksdisplay)

    @property
    def sequencepath(self) -> Optional[str]:
        "return the seqence path"
        return self.sequencemodel.currentpath

    @property
    def sequencekey(self) -> Optional[str]:
        "returns the sequence key"
        return self.sequencemodel.currentkey

    @property
    def oligos(self) -> Optional[Sequence[str]]:
        "return the current probe"
        return self.sequencemodel.currentprobes

    @property
    def hassinglestrand(self) -> bool:
        "return the current probe"
        return "singlestrand" in self.sequencemodel.currentprobes

    def sequences(self, sequence = ...):
        "returns current sequences"
        seqs = self.sequencemodel.currentsequences
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
        if path is None or not Path(path).exists():
            return True
        try:
            seqs = dict(_readsequence(path))
        except IOError:
            return True

        if not len(seqs):
            return True

        them = dict(path  = path, sequences = seqs)
        disp = dict(
            hpins     = {},
            paths     = dict(self._seqdisplay.paths),
            sequences = dict(self._seqdisplay.sequences),
        )

        disp['sequences'][self.roottask] = seqs
        disp['paths'][self.roottask] = path

        if not self.oligos and self.roottask:
            ols = splitoligos("kmer", path = self.roottask.path)
            if ols:
                if ols != self._seqdisplay.probes.get(self.roottask, None):
                    disp['probes'] = {**self._seqdisplay.probes, self.roottask: ols}

                hist            = self._seqconfig.history[:self._seqconfig.maxlength]
                them['history'] = [ols] + [i for i in hist if i != ols]
                if ols != self._seqdisplay.probes:
                    them['probes'] = ols

        # update the display first, otherwise the FitToHairpinTask doesn't get created!
        # see hybridstat.test_peaksview.test_peaksplot_view
        self._updatedisplay(self._seqdisplay, **disp)
        self._updatetheme(self._seqconfig, **them)
        return False

    def setnewsequencekey(self, new):
        "sets new probes"
        hpins = dict(self._seqdisplay.hpins)
        if new is None:
            hpins.pop(self.bead, None)
        else:
            hpins[self.bead] = new
        self._updatedisplay(self._seqdisplay, hpins = hpins)

    def setnewprobes(self, new):
        "sets new probes"
        root = self.roottask
        ols  = splitoligos(new, path = root.path)
        cnf  = self._seqconfig

        disp = self._seqdisplay
        if ols != disp.probes.get(root, None):
            self._updatedisplay(disp, probes = {**disp.probes, root: ols})

        self._updatetheme(
            cnf,
            history = ([ols] if ols else []) + [i for i in cnf.history[:cnf.maxlength] if i != ols],
            **({} if ols == cnf.probes else {'probes': ols})
        )
