#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Base track file data.
"""
from    typing      import (Type, Optional, Union, Dict, Tuple, TypeVar,
                            Generic, cast)
from    copy        import deepcopy, copy as shallowcopy
from    enum        import Enum
import  numpy       as     np

from    utils       import initdefaults
from    model       import levelprop, Level
from   .views       import Beads, Cycles, BEADKEY, isellipsis, TrackView
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
    """
    Characteristics of a bead

    Attributes are:

    * `image` is one image of the field of view
    * `dim` are conversion factors from pixel to nm
    * `beads` is a dictionnary of information per bead:

        * `position` is the bead's (X, Y, Z) position
        * `image` is the bead's calibration image
    """
    position: Tuple[float, float, float] = (0., 0., 0.)
    image:    np.ndarray                 = np.zeros(0, dtype = np.uint8)
    @initdefaults(locals())
    def __init__(self, **_):
        pass

class FoV:
    """
    Data concerning the FoV

    Attributes are:

    * `image` is one image of the field of view
    * `dim` are conversion factors from pixel to nm
    * `beads` is a dictionnary of information per bead:

        * `position` is the bead's (X, Y, Z) position
        * `image` is the bead's calibration image

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
        if self.image is None:
            xpos = [i.position[0] for i in self.beads.values()]
            ypos = [i.position[1] for i in self.beads.values()]
            if len(xpos) and len(ypos):
                return (max(1., np.nanmax(ypos)-np.nanmin(ypos)),
                        max(1., np.nanmax(xpos)-np.nanmin(xpos)))
            return 1., 1.

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

T = TypeVar("T")
class LazyProperty(Generic[T]):
    "Checks whether the file was opened prior to returning a value"
    def __init__(self):
        self.__name = ''

    def __set_name__(self, _, name):
        self.__name = '_'+name

    def __get__(self, obj: 'Track', _) -> T:
        if obj is None:
            return self # type: ignore

        if getattr(obj, '_lazy'):
            setattr(obj, '_lazy', False)
            getattr(obj, 'data') # call property: opens the file
        return getattr(obj, self.__name)

    def __set__(self, obj: 'Track', val) -> T:
        if getattr(obj, '_lazy'):
            setattr(obj, '_lazy', False)
            getattr(obj, 'data') # call property: opens the file
        setattr(obj, self.__name, val)
        return getattr(obj, self.__name)

class ResettingProperty(Generic[T]):
    "Resets all if this attribute is changed"
    def __init__(self):
        self.__name   = ''

    def __set_name__(self, _, name):
        self.__name = '_'+name

    def __get__(self, obj: 'Track', _) -> T:
        return cast(T, getattr(obj, self.__name) if obj else self)

    def __set__(self, obj: 'Track', val) -> T:
        setattr(obj, '_lazy', False)
        setattr(obj, self.__name, cast(T, val))

        for name in ('_framerate', '_phases', '_fov'):
            setattr(obj, name, deepcopy(getattr((type(obj)), name)))

        setattr(obj, '_data', None)
        getattr(obj, '_rawprecisions').clear()
        setattr(obj, '_lazy', True)
        return getattr(self, self.__name)

@levelprop(Level.project)
class Track:
    """
    The data from a track file, accessed lazily (only upon request).

    The data can be read as:

    ```python
    >>> raw = Track(path =  "/path/to/a/file.trk")
    >>> grs = Track(path =  ("/path/to/a/file.trk",
    ...                      "/path/to/a/gr/directory",
    ...                      "/path/to/a/specific/gr"))
    ```

    The data can then be accessed as follows:

    * for the *time* axis: `raw.beads['t']`
    * for the magnet altitude: `raw.beads['zmag']`
    * specific beads: `raw.beads[0]` where 0 can be any bead number
    * specific cycles: `raw.cycles[1,5]` where 1 and 5 can be any bead or cycle number.

    Some slicing is possible:

    * `raw.cycles[:,range(5,10)]` accesses cycles 5 though 10 for all beads.
    * `raw.cycles[[2,5],...]` accesses all cycles for beads 5 and 5.

    Only data for the Z axis is available. Use the `axis = 'X'` or `axis = 'Y'`
    options in the constructor to access other data.

    Other attributes are:

    * `framerate` is this experiment's frame rate
    * `fov` is the field of view data:

        * `image` is one image of the field of view
        * `dim` are conversion factors from pixel to nm
        * `beads` is a dictionnary of information per bead:

            * `position` is the bead's (X, Y, Z) position
            * `image` is the bead's calibration image
    """
    _framerate                  = 30.
    _fov: FoV                   = None
    _phases                     = np.empty((0,9), dtype = 'i4')
    _data:          DATA        = None
    _path:          PATHTYPES   = None
    _rawprecisions: _PRECISIONS = {}
    _lazy                       = True
    _axis                       = Axis.Zaxis
    key:            str         = None
    @initdefaults(( 'key'), **{i: '_' for i in _LAZIES + ('phases', 'axis')})
    def __init__(self, **_) -> None:
        pass

    def __getstate__(self):
        info = self.__dict__.copy()
        for name in _LAZIES:
            val = info.pop('_'+name)
            if val !=  getattr(type(self), '_'+name):
                info[name] = val

        info['axis'] = info.pop('_axis').value
        val = info.pop('_phases')
        if len(val) > 0:
            info['phases'] = val

        if 'path' in info:
            info.pop('data', None)
        return info

    def __setstate__(self, values):
        self.__init__(**values)

    phases    = LazyProperty[np.ndarray]()
    framerate = LazyProperty[float]()
    fov       = LazyProperty[FoV]()
    path      = ResettingProperty[Optional[PATHTYPES]]()
    axis      = ResettingProperty[Axis]()
    ncycles   = cast(int, property(lambda self: len(self.phases)))
    nphases   = cast(int, property(lambda self: self.phases.shape[1]))

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

    def phaseduration(self, cid:IDTYPE, pid:IDTYPE) -> Union[int, np.ndarray]:
        "returns the duration of the cycle and phase"
        phases = self.phases
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
        vect = self.phases
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
    def beads(self) -> Beads:
        "returns a helper object for extracting beads"
        return self.view(Beads, beadsonly = False)

    @property
    def beadsonly(self) -> Beads:
        "returns a helper object for extracting beads from *beads* only"
        return self.view(Beads, beadsonly = True)

    @property
    def cycles(self) -> Cycles:
        "returns a helper object for extracting cycles"
        return self.view(Cycles, beadsonly = False)

    @property
    def cyclesonly(self) -> Cycles:
        "returns a helper object for extracting cycles from *beads* only"
        return self.view(Cycles, beadsonly = True)

    def view(self, tpe:Union[Type[TrackView], str], **kwa):
        "Creates a view of the suggested type"
        viewtype = (tpe     if isinstance(tpe, type) else
                    Cycles  if tpe.lower() == 'cycles' else
                    Beads)
        kwa.setdefault('parents', (self.key,) if self.key else (self.path,))
        kwa.setdefault('track',   self)
        return viewtype(**kwa)

def dropbeads(trk, *beads:Tuple[BEADKEY]) -> Track:
    "returns a track without the given beads"
    cpy           = shallowcopy(trk)
    good          = frozenset(trk.data.keys()) - frozenset(beads)
    cpy.data      = {i: cpy.data[i] for i in good}

    cpy.fov       = shallowcopy(trk.fov)
    good          = good & frozenset(cpy.fov.beads)
    cpy.fov.beads = {i: cpy.fov.beads[i] for i in good}
    return cpy
