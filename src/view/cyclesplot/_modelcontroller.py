#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"access to the model"

from typing         import Optional, Sequence, Tuple, cast

from   utils        import NoArgs
from  ..plotutils   import TrackPlotModelController, readsequence

def _configprop(attr):
    "returns a property which links to the config"
    def _getter(self):
        return self.getConfig()[attr].get()
    def _setter(self, val):
        self.getConfig()[attr].set(val)
    hmsg  = "link to config's {}".format(attr)
    return property(_getter, _setter, None, hmsg)

def _beadorconfig(attr):
    "returns a property which links to the current bead or the config"
    def _getter(self):
        value = self.getCurrent()[attr].get().get(self.bead, NoArgs)
        if value is not NoArgs:
            return value
        return self.getConfig()[attr].get()

    def _setter(self, val):
        cache = self.getCurrent()[attr].get()
        if val == self.getConfig()[attr].get():
            cache.pop(self.bead, None)
        else:
            cache[self.bead] = val
    hmsg  = "link to config's {}".format(attr)
    return property(_getter, _setter, None, hmsg)

class CyclesModelController(TrackPlotModelController):
    "Model for Cycles View"
    _CACHED = 'base.stretch', 'base.bias', 'sequence.key', 'sequence.witnesses'
    def __init__(self, ctrl, key):
        super().__init__(ctrl, key)
        self.getConfig().defaults = {'binwidth'          : .003,
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
        self.getConfig().sequence.witnesses.default = None
        for attr in self._CACHED:
            self.getCurrent()[attr].setdefault(None)
        self.clearcache()

    def clearcache(self):
        u"updates the model when a new track is loaded"
        self.getCurrent().update({i: dict() for i in self._CACHED})

    binwidth     = cast(float,                   _configprop  ('binwidth'))
    minframes    = cast(int,                     _configprop  ('minframes'))
    sequencepath = cast(Optional[str],           _configprop  ('sequence.path'))
    oligos       = cast(Optional[Sequence[str]], _configprop  ('oligos'))
    stretch      = cast(float,                   _beadorconfig('base.stretch'))
    bias         = cast(Optional[float],         _beadorconfig('base.bias'))
    witnesses    = cast(Optional[Tuple[float,float,float,float]],
                        _beadorconfig('sequence.witnesses'))

    _sequencekey = cast(Optional[str],           _beadorconfig('sequence.key'))
    @property
    def sequencekey(self) -> Optional[str]:
        "returns the current sequence key"
        key  = self._sequencekey
        dseq = readsequence(self.sequencepath)
        if key not in dseq:
            return next(iter(dseq), None)

    @sequencekey.setter
    def sequencekey(self, value) -> Optional[str]:
        self._sequencekey = value
        return self._sequencekey
