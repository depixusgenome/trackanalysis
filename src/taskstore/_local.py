#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Local patch mechanism
"""
from copy    import copy
from typing  import Optional, Callable, Sequence, cast

from utils    import initdefaults
from anastore import CNT, modifyclasses, Patches, DELETE

class LocalPatch:
    """
    define a local patch. NOT THREADSAFE
    """
    modifications    = ("peakcalling.processor.fittoreference.FitToReferenceTask", DELETE,
                        "peakcalling.processor.fittohairpin.FitToHairpinTask",     DELETE)
    path:    Optional[Callable[[Sequence[str]], Sequence[str]]] = None
    patches: Optional[Patches]                                  = None
    _old:    Patches

    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        pass

    def _modify(self, data:dict) -> dict:
        mods = tuple(self.modifications)
        if self.path is not None: # type: ignore
            def _pathpatch(val):
                # pylint: disable=not-callable
                val[CNT] = self.path(cast(Sequence[str], val[CNT])) # type: ignore
                return val
            mods += "taskmodel.track.TrackReaderTask", dict(path = _pathpatch)
        modifyclasses(data, *mods)
        return data

    def __enter__(self):
        if self.patches is None:
            from ._default import __TASKS__ as patches
        else:
            patches = self.patches

        self._old = copy(patches)
        patches.patch(self._modify)
        return patches

    def __exit__(self, *_):
        if self.patches is None:
            from ._default import __TASKS__ as patches
        else:
            patches = self.patches
        patches.__dict__.update(self._old.__dict__)
