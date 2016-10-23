#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"""
Base track file data.
"""
from    typing import Optional # pylint: disable=unused-import
import  pickle
import  numpy   # type: ignore

import  legacy  # type: ignore # pylint: disable=import-error
from    model       import levelprop, Level
from   .trackitems  import Beads, Cycles

@levelprop(Level.project)
class Track:
    "Model for track files. This must not contain actual data."
    def __init__(self, **kw) -> None:
        self._path      = kw.get('path', None)  # type: Optional[str]
        self._data      = None                  # type: Optional[Dict]
        self._cycles    = None                  # type: ignore

    @property
    def frequency(self):
        u"returns the camera frequency"
        return self._frequency

    @property
    def nphases(self):
        u"returns the number of phases in the track"
        return self._nphases

    @property
    def path(self):
        u"returns the path to the trackfile"
        return self._path

    def phaseid(self, cid:int, pid:int) -> int:
        u"returns the path to the trackfile"
        return self._cycles[cid,pid]-self._cycles[0,0] # pylint: disable=unsubscriptable-object

    @property
    def data(self):
        u"returns the dataframe with all bead info"
        if self._data is None and self._path is not None:
            if self._path.endswith(".pk"):
                with open(self._path, 'rb') as stream:
                    kwargs = pickle.load(stream)
            else:
                kwargs = legacy.readtrack(self._path)

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
