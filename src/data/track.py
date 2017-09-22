#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Base track file data.
"""
from    typing      import Optional, Union, Dict, Tuple
from    copy        import deepcopy, copy as shallowcopy
from    enum        import Enum
import  numpy       as     np

from    utils       import initdefaults
from    model       import levelprop, Level
from   .views       import Beads, Cycles, BEADKEY, isellipsis
from   .trackio     import opentrack, PATHTYPES

IDTYPE       = Union[None, int, slice] # missing Ellipsys as mypy won't accept it
DATA         = Dict[BEADKEY, np.ndarray]
BEADS        = Dict[BEADKEY, 'Bead']
DIMENSIONS   = Tuple[Tuple[float, float], Tuple[float, float]]
_PRECISIONS  = Dict[BEADKEY, float]
_LAZIES      = ('fov',  'framerate', 'data', 'path', 'lazy', 'rawprecisions')

class Axis(Enum):
    "which axis to look at"
    Xaxis = 'Xaxis'
    Yaxis = 'Yaxis'
    Zaxis = 'Zaxis'
    @classmethod
    def _missing_(cls, name):
        if name in 'xyz':
            name = name.upper()
        if name in 'XYZ':
            name += 'axis'
        return cls(name)

class Bead:
    "characteristics of a bead"
    position: Tuple[float, float, float] = (0., 0., 0.)
    image:    np.ndarray                 = np.zeros(0, dtype = np.uint8)
    @initdefaults(locals())
    def __init__(self, **_):
        pass

class FoV:
    """
    Data concerning the FoV

    Dimensions are provided as : (X slope, X bias), (Y slope, Y bias)
    """
    image                       = np.empty((0,0), dtype = np.uint8)
    beads:         BEADS        = {}
    dim:           DIMENSIONS   = ((1., 0.), (1., 0.))
    @initdefaults(locals())
    def __init__(self, **kwa):
        pass

    def bounds(self, pixel = False):
        "image bounds in nm (*pixel == False*) or pixels"
        rng = self.image.shape[1], self.image.shape[0]
        return (0, 0) + rng if pixel else self.tonm((0,0))+ self.tonm(rng)

    def size(self, pixel = False):
        "image size in nm (*pixel == False*) or pixels"
        rng = self.image.shape[1], self.image.shape[0]
        return rng if pixel else self.tonm(rng)

    def tonm(self, arr):
        "converts pixels to nm"
        return self.__convert(arr, self.dim)

    def topixel(self, arr):
        "converts pixels to nm"
        return self.__convert(arr, tuple((1./i, -j/i) for i, j in self.dim))

    @property
    def scale(self):
        "The pixel scale: error occurs if the pixel is not square"
        if abs(self.dim[0][0]-self.dim[1][0]) > 1e-6:
            raise ValueError("Pixel is not square")
        return self.dim[0][0]

    @staticmethod
    def __convert(arr, dim):
        if len(arr) == 0:
            return arr

        (sl1, int1), (sl2, int2) = dim
        if isinstance(arr, np.ndarray):
            return [sl1, sl2] * arr + [int1, int2]

        if isinstance(arr, tuple) and len(arr) == 2 and np.isscalar(arr[0]):
            return tuple(i*k+j for (i, j), k in zip(dim, arr))

        tpe = iter if hasattr(arr, '__next__') else type(arr)
        return tpe([(sl1*i+int1, sl2*j+int2) for i, j in arr]) # type: ignore

@levelprop(Level.project)
class Track:
    "Model for track files. This must not contain actual data."
    _framerate                  = 30.
    _fov: FoV                   = None
    _phases                     = np.empty((0,9), dtype = 'i4')
    _data:          DATA        = None
    _path:          PATHTYPES   = None
    _rawprecisions: _PRECISIONS = {}
    _lazy                       = True
    key:            str         = None
    axis                        = Axis.Zaxis
    @initdefaults(('axis', 'key'), **{i: '_' for i in _LAZIES + ('phases',)})
    def __init__(self, **_) -> None:
        pass

    def __getstate__(self):
        info = self.__dict__.copy()
        for name in _LAZIES:
            val = info.pop('_'+name)
            if val !=  getattr(type(self), '_'+name):
                info[name] = val

        info['axis'] = info['axis'].value
        val = info.pop('_phases')
        if len(val) > 0:
            info['phases'] = val

        if 'path' in info:
            info.pop('data', None)
        return info

    def __setstate__(self, values):
        self.__init__(**values)

    def __getter(self, name):
        if self._lazy:
            self._lazy = False
            getattr(self, 'data') # call property: opens the file
        return getattr(self, name)

    def __setter(self, name, val):
        if self._lazy:
            self._lazy = False
            getattr(self, 'data') # call property: opens the file
        setattr(self, name, val)
        return getattr(self, name)

    @property
    def phases(self) -> np.ndarray:
        "returns the number of cycles in the track file"
        return self.__getter('_phases')

    @phases.setter
    def phases(self, val) -> np.ndarray:
        "returns the number of cycles in the track file"
        return self.__setter('_phases', val)

    @property
    def framerate(self) -> float:
        "returns the frame rate"
        return self.__getter('_framerate')

    @framerate.setter
    def framerate(self, val) -> float:
        "returns the frame rate"
        val = self.__setter('_framerate', val)
        if val <= 0.:
            raise ValueError("Track.framerate <= 0.")
        return val

    @property
    def fov(self) -> FoV:
        "returns the FoV"
        return self.__getter('_fov')

    @fov.setter
    def fov(self, val) -> FoV:
        "returns the FoV"
        return self.__setter('_fov', val)

    @property
    def ncycles(self) -> int:
        "returns the number of cycles in the track file"
        return len(self.__getter('_phases'))

    @property
    def nphases(self) -> Optional[int]:
        "returns the number of phases in the track"
        return self.__getter('_phases').shape[1]

    def phaseduration(self, cid:IDTYPE, pid:IDTYPE) -> Union[int, np.ndarray]:
        "returns the duration of the cycle and phase"
        phases = self.__getter('_phases')
        if isellipsis(pid):
            ix1, ix2 = 0, -1
        elif isinstance(pid, int):
            if pid in (-1, phases.shape[1]):
                return np.insert(phases[0,1:]-phases[-1,:-1], len(phases), np.iinfo('i4').max)
            else:
                ix1, ix2 = pid, pid+1
        return phases[cid,ix2]-phases[cid,ix1]

    def phase(self, cid:IDTYPE = None, pid:IDTYPE = None) -> Union[np.ndarray, int]:
        "returns the starttime of the cycle and phase"
        vect = self.__getter('_phases')
        orig = vect[0,0]
        ells = isellipsis(cid), isellipsis(pid)
        if all(ells):
            pass
        elif ells[0]:
            vect = vect[:,pid]
        elif ells[1]:
            vect = vect[cid,:]
        else:
            vect = vect[cid,pid]
        return vect - orig

    @property
    def path(self) -> Optional[PATHTYPES]:
        "returns the current path(s)"
        return self._path

    @path.setter
    def path(self, val) -> Optional[PATHTYPES]:
        "sets the current path(s) and clears the data"
        self._lazy = False
        self._path = val

        for name in ('_framerate', '_phases', '_fov'):
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

    def __view(self, tpe, **kwa):
        parents = (self.key,) if self.key else (self.path,)
        return tpe(track = self, parents = parents, **kwa)

    @property
    def beads(self) -> Beads:
        "returns a helper object for extracting beads"
        return self.__view(Beads, beadsonly = False)

    @property
    def beadsonly(self) -> Beads:
        "returns a helper object for extracting beads from *beads* only"
        return self.__view(Beads, beadsonly = True)

    @property
    def cycles(self) -> Cycles:
        "returns a helper object for extracting cycles"
        return self.__view(Cycles, beadsonly = False)

    @property
    def cyclesonly(self) -> Cycles:
        "returns a helper object for extracting cycles from *beads* only"
        return self.__view(Cycles, beadsonly = True)

def dropbeads(trk, *beads:Tuple[BEADKEY]) -> Track:
    "returns a track without the given beads"
    cpy           = shallowcopy(trk)
    good          = frozenset(trk.data.keys()) - frozenset(beads)
    cpy.data      = {i: cpy.data[i] for i in good}

    cpy.fov       = shallowcopy(trk.fov)
    good          = good & frozenset(cpy.fov.beads)
    cpy.fov.beads = {i: cpy.fov.beads[i] for i in good}
    return cpy
