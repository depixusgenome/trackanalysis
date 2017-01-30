#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"""
Base track file data.
"""
from    typing import Optional  # pylint: disable=unused-import
import  pickle
import  numpy                   # type: ignore

from    legacy      import readtrack   # pylint: disable=import-error,no-name-in-module
from    model       import levelprop, Level
from   .trackitems  import Beads, Cycles

@levelprop(Level.project)
class Track:
    "Model for track files. This must not contain actual data."
    def __init__(self, **kwa) -> None:
        self._path      = kwa.get('path',       None) # type: Optional[str]
        self._data      = kwa.get('data',       None) # type: Optional[Dict]
        self._cycles    = kwa.get('cycles',     None) # type: ignore
        self._frequency = kwa.get('frequency',  None) # type: Optional[float]

    @property
    def frequency(self) -> 'Optional[float]':
        u"returns the camera frequency"
        return self._frequency

    @property
    def nphases(self) -> 'Optional[int]':
        u"returns the number of phases in the track"
        return None if self._cycles is None else self._cycles.shape[1]

    @property
    def path(self) -> 'Optional[str]':
        u"returns the path to the trackfile"
        return self._path

    @property
    def phaseids(self):
        u"returns all phase ids, undoctored"
        return self._cycles[:]

    def phaseid(self, cid:'Optional[int]' = None, pid:'Optional[int]' = None):
        u"returns the starttime of the cycle and phase"
        vect = self._cycles
        orig = vect[0,0]
        if {cid, pid}.issubset((all, None)):
            pass
        elif cid in (all, None):
            vect = vect[:,pid]
        elif pid in (all, None):
            vect = vect[cid,:]
        else:
            vect = vect[cid,pid]
        return vect - orig

    @property
    def data(self):
        u"returns the dataframe with all bead info"
        if self._data is None and self._path is not None:
            if self._path.endswith(".pk"):
                with open(self._path, 'rb') as stream:
                    kwargs = pickle.load(stream)
            else:
                kwargs = readtrack(self._path)

            if kwargs is None:
                self._data = dict()

            else:
                for name in ('cycles', 'frequency'):
                    setattr(self, '_'+name, kwargs.pop(name))

                self._data = dict(ite for ite in kwargs.items()
                                  if isinstance(ite[1], numpy.ndarray))
        return self._data

    @staticmethod
    def isbeadname(key) -> bool:
        u"returns whether a column name is a bead's"
        return isinstance(key, int)

    @property
    def ncycles(self):
        u"returns the number of cycles in the track file"
        return len(self._cycles)

    @property
    def beads(self) -> Beads:
        u"returns a helper object for extracting beads"
        return Beads(track = self, parents = (self.path,))

    @property
    def cycles(self) -> Cycles:
        u"returns a helper object for extracting cycles"
        return Cycles(track = self, parents = (self.path,))
