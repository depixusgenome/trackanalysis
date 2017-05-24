#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Base track file data.
"""
from    typing      import Optional, Union, Dict, Tuple
from    copy        import deepcopy
import  numpy       as     np

from    utils       import initdefaults
from    model       import levelprop, Level
from   .trackitems  import Beads, Cycles, BEADKEY, _m_ALL
from   .trackio     import opentrack

IDTYPE = Union[None, int, slice] # missing Ellipsys as mypy won't accept it

@levelprop(Level.project)
class Track:
    "Model for track files. This must not contain actual data."
    _framerate     = 0.
    _phases        = np.empty((0,9), dtype = 'i4')
    _data          = None # type: Optional[Dict[BEADKEY, np.ndarray]]
    _path          = None # type: Union[str, Tuple[str, ...]]
    _rawprecisions = {}   # type: Dict[BEADKEY, float]
    _lazy          = True
    @initdefaults(tuple(),
                  framerate     = '_',
                  phases        = '_',
                  data          = '_',
                  path          = '_',
                  lazy          = '_',
                  rawprecisions = '_')
    def __init__(self, **_) -> None:
        pass

    def __getstate__(self):
        info = self.__dict__.copy()
        for name in ('path', 'framerate', 'rawprecisions', 'data', 'lazy'):
            val = info.pop('_'+name)
            if val !=  getattr(type(self), '_'+name):
                info[name] = val

        val = info.pop('_phases')
        if len(val) > 0:
            info['phases'] = val

        if 'path' in info:
            info.pop('data', None)
        return info

    def __setstate__(self, values):
        self.__init__(**values)

    def __unlazyfy(self):
        if self._lazy:
            self._lazy = False
            getattr(self, 'data') # call property: opens the file

    @property
    def phases(self) -> np.ndarray:
        "returns the number of cycles in the track file"
        self.__unlazyfy()
        return self._phases

    @phases.setter
    def phases(self, vals) -> np.ndarray:
        "returns the number of cycles in the track file"
        self.__unlazyfy()
        self._phases = vals
        return self._phases

    @property
    def framerate(self) -> float:
        "returns the frame rate"
        self.__unlazyfy()
        return self._framerate

    @framerate.setter
    def framerate(self, val) -> float:
        "returns the frame rate"
        self.__unlazyfy()
        self._framerate = val
        return self._framerate

    @property
    def ncycles(self) -> int:
        "returns the number of cycles in the track file"
        self.__unlazyfy()
        return len(self._phases)

    @property
    def nphases(self) -> Optional[int]:
        "returns the number of phases in the track"
        self.__unlazyfy()
        return self._phases.shape[1]

    def phaseduration(self, cid:IDTYPE, pid:IDTYPE) -> Union[int, np.ndarray]:
        "returns the duration of the cycle and phase"
        self.__unlazyfy()

        if pid in _m_ALL:
            ix1, ix2 = 0, -1
        elif isinstance(pid, int):
            if pid in (-1, self._phases.shape[1]):
                return np.insert(self._phases[0,1:]-self._phases[-1,:-1],
                                 len(self._phases), np.iinfo('i4').max)
            else:
                ix1, ix2 = pid, pid+1
        return self._phases[cid,ix2]-self._phases[cid,ix1]

    def phase(self, cid:IDTYPE = None, pid:IDTYPE = None) -> Union[np.ndarray, int]:
        "returns the starttime of the cycle and phase"
        self.__unlazyfy()
        vect = self._phases
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
    def path(self) -> Union[None, str, Tuple[str, ...]]:
        "returns the current path(s)"
        return self._path

    @path.setter
    def path(self, val) -> Union[None, str, Tuple[str, ...]]:
        "sets the current path(s) and clears the data"
        self._lazy = False
        self._path = val

        for name in ('_framerate', '_phases'):
            setattr(self, name, deepcopy(getattr((type(self)), name)))

        self._data = None
        self._rawprecisions.clear()
        self._lazy = True
        return self._path

    @property
    def data(self) -> Dict:
        "returns the dataframe with all bead info"
        if self._data is None and self._path is not None:
            opentrack(self)
        return self._data

    @data.setter
    def data(self, data: Optional[Dict[BEADKEY, np.ndarray]]):
        "sets the dataframe"
        self._data = data
        self._rawprecisions.clear()

    @staticmethod
    def isbeadname(key) -> bool:
        "returns whether a column name is a bead's"
        return isinstance(key, int)

    @property
    def beads(self) -> Beads:
        "returns a helper object for extracting beads"
        return Beads(track = self, parents = (self.path,), beadsonly = False)

    @property
    def beadsonly(self) -> Beads:
        "returns a helper object for extracting beads from *beads* only"
        return Beads(track = self, parents = (self.path,), beadsonly = True)

    @property
    def cycles(self) -> Cycles:
        "returns a helper object for extracting cycles"
        return Cycles(track = self, parents = (self.path,))

    @property
    def cyclesonly(self) -> Cycles:
        "returns a helper object for extracting cycles from *beads* only"
        return Cycles(track = self, parents = (self.path,), beadsonly = True)
