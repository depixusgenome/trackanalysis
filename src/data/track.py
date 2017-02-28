#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"""
Base track file data.
"""
from    typing      import Optional, Union, Dict
import  numpy       as     np

from    utils       import initdefaults
from    model       import levelprop, Level
from   .trackitems  import Beads, Cycles, BEADKEY, _m_ALL
from   .trackio     import opentrack

IDTYPE = Union[None, int, slice] # missing Ellipsys as mypy won't accept it

@levelprop(Level.project)
class Track:
    "Model for track files. This must not contain actual data."
    path      = ''
    framerate = 0.
    phases    = np.empty((0,9), dtype = 'i4')
    _data     = None # type: Optional[Dict[BEADKEY,np.ndarray]]
    @initdefaults
    def __init__(self, **kwa) -> None:
        self._data = kwa.get('data', None)

    @property
    def ncycles(self) -> int:
        u"returns the number of cycles in the track file"
        return len(self.phases)

    @property
    def nphases(self) -> Optional[int]:
        u"returns the number of phases in the track"
        return self.phases.shape[1]

    def phaseduration(self, cid:IDTYPE, pid:IDTYPE) -> Union[int, np.ndarray]:
        u"returns the duration of the cycle and phase"
        if pid in _m_ALL:
            ix1, ix2 = 0, -1
        elif isinstance(pid, int):
            if pid in (-1, self.phases.shape[1]):
                return np.insert(self.phases[0,1:]-self.phases[-1,:-1],
                                 len(self.phases), np.iinfo('i4').max)
            else:
                ix1, ix2 = pid, pid+1
        return self.phases[cid,ix2]-self.phases[cid,ix1]

    def phase(self, cid:IDTYPE = None, pid:IDTYPE = None) -> Union[np.ndarray, int]:
        u"returns the starttime of the cycle and phase"
        vect = self.phases
        orig = vect[0,0]
        if {cid, pid}.issubset(_m_ALL):
            pass
        elif cid in _m_ALL:
            vect = vect[:,pid]
        elif pid in _m_ALL:
            vect = vect[cid,:]
        else:
            vect = vect[cid,pid]
        return vect - orig

    @property
    def data(self):
        u"returns the dataframe with all bead info"
        if self._data is None and self.path is not None:
            opentrack(self)

        return self._data

    @data.setter
    def data(self, data: Optional[Dict[BEADKEY,np.ndarray]]):
        u"sets the dataframe"
        self._data = data

    @staticmethod
    def isbeadname(key) -> bool:
        u"returns whether a column name is a bead's"
        return isinstance(key, int)

    @property
    def beads(self) -> Beads:
        u"returns a helper object for extracting beads"
        return Beads(track = self, parents = (self.path,), beadsonly = False)

    @property
    def beadsonly(self) -> Beads:
        u"returns a helper object for extracting beads from *beads* only"
        return Beads(track = self, parents = (self.path,), beadsonly = True)

    @property
    def cycles(self) -> Cycles:
        u"returns a helper object for extracting cycles"
        return Cycles(track = self, parents = (self.path,))

    @property
    def cyclesonly(self) -> Cycles:
        u"returns a helper object for extracting cycles from *beads* only"
        return Cycles(track = self, parents = (self.path,), beadsonly = True)
