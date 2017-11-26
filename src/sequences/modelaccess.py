#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Access to oligos and sequences"
from typing                 import Optional, Sequence, cast
from pathlib                import Path
from abc                    import abstractmethod
from collections            import OrderedDict

from utils                  import CachedIO
from control.modelaccess    import TaskPlotModelAccess
from model.globals          import ConfigRootProperty, BeadProperty, RootTaskProperty
from .                      import read as _readsequence, peaks as _sequencepeaks

_CACHE = CachedIO(lambda path: OrderedDict(_readsequence(path)), size = 1)
def readsequence(path):
    "Reads / caches DNA sequences"
    if path is None or not Path(path).exists():
        return dict()
    try:
        return _CACHE(path)
    except: # pylint: disable=bare-except
        return dict()

class SequencePathProperty(ConfigRootProperty):
    "access to the sequence path"
    def __init__(self):
        super().__init__('tasks.sequence.path')

    def __get__(self, obj, tpe) -> Optional[str]:
        cur = super().__get__(obj, tpe)
        return cur if obj is None or (cur is not None and Path(cur).exists()) else None

class SequencePlotModelAccess(TaskPlotModelAccess):
    "access to the sequence path and the oligo"
    sequencepath = cast(Optional[str],           SequencePathProperty())
    oligos       = cast(Optional[Sequence[str]], RootTaskProperty("tasks.oligos"))

    def __init__(self, ctrl, key: str = None) -> None:
        super().__init__(ctrl, key)
        cls = type(self)
        cls.sequencepath.setdefault(self, None)         # type: ignore
        cls.oligos      .setdefault(self, [], size = 4) # type: ignore

    def sequences(self, sequence = ...):
        "returns current sequences"
        seqs = readsequence(self.sequencepath)
        if sequence is Ellipsis:
            return seqs
        return seqs.get(self.sequencekey if sequence is None else sequence, None)

    def hybridisations(self, sequence = ...):
        "returns the peaks"
        seqs = self.sequences(...)
        if len(seqs) == 0:
            return None

        ols = self.oligos
        if ols is None or len(ols) == 0:
            return None

        if sequence is Ellipsis:
            return {i: _sequencepeaks(j, ols) for i, j in seqs.items()}

        key = sequence if sequence is not None else self.sequencekey
        if key is None:
            return None
        return _sequencepeaks(seqs[key], ols)

    @property
    @abstractmethod
    def sequencekey(self) -> Optional[str]:
        "returns the sequence key"

    def setnewsequencepath(self, path):
        "sets a new path if it is correct"
        seqs = dict(readsequence(path))
        if len(seqs) > 0:
            self.sequencepath = path
            self.sequencekey  = next(iter(seqs))
            return False
        return True

class SequenceKeyProp(BeadProperty):
    "access to the sequence key"
    def __init__(self):
        super().__init__('sequence.key')

    def fromglobals(self, obj) -> Optional[str]:
        "returns the current sequence key stored in globals"
        return super().__get__(obj, None)

    def __get__(self, obj, tpe) -> Optional[str]:
        "returns the current sequence key"
        if obj is None:
            return self # type: ignore

        key  = self.fromglobals(obj)
        if key is not None:
            return key

        dseq = dict(readsequence(obj.sequencepath))
        return next(iter(dseq), None) if key not in dseq else key

class FitParamProp(BeadProperty):
    "access to bias or stretch"
    def __init__(self, attr):
        super().__init__('base.'+attr)
        self._key = attr

    def __get__(self, obj, tpe) -> Optional[float]:  # type: ignore
        val = cast(float, super().__get__(obj, tpe))
        if val is None:
            return getattr(obj, 'estimated'+self._key)
        return cast(float, val)

    def setdefault(self, obj, # type: ignore # pylint: disable=arguments-differ
                   items:Optional[dict] = None,
                   **kwa):
        "initializes the property stores"
        super().setdefault(obj,
                           (None if self._key == 'bias' else 1./8.8e-4),
                           items,
                           **kwa)
