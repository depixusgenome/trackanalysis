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
    def __init__(self, **kw) -> None:
        self._path      = kw.get('path', None)  # type: Optional[str]
        self._data      = None                  # type: Optional[Dict]
        self._cycles    = None                  # type: ignore
        self._frequency = None                  # type: Optional[float]
        self._nphases   = None                  # type: Optional[int]

    @property
    def frequency(self) -> 'Optional[float]':
        u"returns the camera frequency"
        return self._frequency

    @property
    def nphases(self) -> 'Optional[int]':
        u"returns the number of phases in the track"
        return self._nphases

    @property
    def path(self) -> 'Optional[str]':
        u"returns the path to the trackfile"
        return self._path

    def phaseid(self, cid:int, pid:int):
        u"returns the starttime of the cycle and phase"
        # pylint: disable=unsubscriptable-object
        if cid in (all, None):
            if pid in (all, None):
                return self._cycles - self._cycles[0,0]
            else:
                return self._cycles[:,pid]-self._cycles[0,0]
        elif pid in (all, None):
            return self._cycles[cid,:]-self._cycles[0,0]
        else:
            return self._cycles[cid,pid]-self._cycles[0,0]

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
                for name in ('cycles', 'nphases', 'frequency'):
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
