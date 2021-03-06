#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Base track file data.
"""
from    typing      import (
    Type, Optional, Union, Dict, Tuple, Any, List,
    Sequence, Iterable, Iterator, cast, overload
)
from    datetime    import datetime
from    pathlib     import Path
from    copy        import deepcopy, copy
from    enum        import Enum
import  numpy       as     np

from    taskmodel       import levelprop, Level, InstrumentType
from    taskmodel.level import PHASE
from    utils           import initdefaults, NoArgs
from   .views           import Beads, Cycles, isellipsis, TrackView
from   .trackio         import opentrack, PATHTYPES, instrumentinfo
from   .beadstats       import (
    RawPrecisionCache  as _RawPrecisionCache,
    beadextension as _beadextension,
    phaseposition as _phaseposition,
)

IDTYPE       = Union[None, int, range]  # missing Ellipsys as mypy won't accept it
PIDTYPE      = Union[IDTYPE, slice, Sequence[int]]

DATA         = Dict[int, np.ndarray]
BEADS        = Dict[int, 'Bead']
DIMENSIONS   = Tuple[Tuple[float, float], Tuple[float, float]]


def _doc(tpe: type) -> str:
    if tpe.__doc__:
        doc = cast(str, tpe.__doc__).strip()
        return doc[0].lower()+doc[1:].replace('\n', '\n    ')+"\n"
    return ''

def _lazies():
    return ('_data', '_rawprecisions') + tuple(LazyProperty.LIST)


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
    Characteristics of a bead:

    * `position` is the bead's (X, Y, Z) position
    * `image` is the bead's calibration image
    """
    position: Tuple[float, float, float] = (0., 0., 0.)
    image:    np.ndarray                 = np.zeros(0, dtype = np.uint8)

    @initdefaults(locals())
    def __init__(self, **_):
        pass

    def thumbnail(self, size, fov):
        "extracts a thumbnail around the bead position"
        pos  = fov.topixel(np.array(list(self.position[:2])))
        ind  = np.int32(np.round(pos))-size//2  # type: ignore
        return fov.image[ind[1]:ind[1]+size,ind[0]:ind[0]+size]

class FoV:
    """
    The data concerning the field of view:

    * `image` is one image of the field of view
    * `dim` are conversion factors from pixel to nm in the format:
    "(X slope, X bias), (Y slope, Y bias)".
    * `beads` is a dictionnary of information per bead:
    """
    if __doc__:
        __doc__ += ''.join(f'    {i}\n' for i in cast(str, Bead.__doc__).split('\n')[-4:])

    image                       = np.empty((0,0), dtype = np.uint8)
    beads:         BEADS        = {}
    dim:           DIMENSIONS   = ((1., 0.), (1., 0.))

    @initdefaults(locals())
    def __init__(self, **kwa):
        pass

    def bounds(self, pixel = False):
        "image bounds in nm (*pixel == False*) or pixels"
        rng = self.image.shape[1], self.image.shape[0]
        return (0, 0) + rng if pixel else self.tonm((0,0)) + self.tonm(rng)

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
        return tpe([(sl1*i+int1, sl2*j+int2) for i, j in arr])  # type: ignore

class Secondaries:
    """
    Consists in arrays of sparse measures:

    * `track.secondaries.tservo` is the servo temperature
    * `track.secondaries.tsample` is the sample temperature
    * `track.secondaries.tsink` is the heat sink temperature
    * `track.secondaries.vcap` is a measure of magnet altitude using voltages
    * `track.secondaries.zmag` is a measure of magnet altitude provided by its motor
    * `track.secondaries.seconds` is the time axis
    """
    def __init__(self, track):
        self.__track = track

    data    = property(lambda self: self.__track._secondaries,
                       doc = "returns all the data")
    tservo  = cast(np.ndarray, property(lambda self: self.__value("Tservo"),
                                        doc = "the servo temperature"))
    tsample = cast(np.ndarray, property(lambda self: self.__value("Tsample"),
                                        doc = "the sample temperature"))
    tsink   = cast(np.ndarray, property(lambda self: self.__value("Tsink"),
                                        doc = "the sink temperature"))
    vcap    = cast(np.ndarray, property(lambda self: self.data.get("vcap"),
                                        doc = "the magnet position: vcap"))
    frames  = cast(np.ndarray, property(lambda self: self.__track._secondaries["t"],
                                        doc = "the time axis (frame count)"))
    seconds = cast(
        np.ndarray,
        property(
            lambda self: (self.__track._secondaries["t"] / self.__track.framerate),
            doc = "the time axis (s)"
        )
    )
    zmag    = cast(np.ndarray, property(lambda self: self.__track._secondaries["zmag"],
                                        doc = "the magnet altitude sampled at frame rate"))

    @property
    def cid(self) -> np.ndarray:
        "return the cycle per frame"
        arr = np.zeros(self.__track.nframes, dtype = 'i4')
        for i, j  in enumerate(np.split(
                arr,
                self.__track.phases[:,0]-self.__track.phases[0,0]
        )[1:]):
            j[:] = i
        return arr

    @property
    def cycleframe(self) -> np.ndarray:
        "return the frame-number per cycle, with each cycle starting at 0"
        arr = np.zeros(self.__track.nframes, dtype='i4')
        for j in np.split(
                arr,
                self.__track.phases[:, 0]-self.__track.phases[0, 0]
        )[1:]:
            j[:] = np.arange(len(j))
        return arr

    @property
    def cidcycles(self) -> Cycles:
        "return the phases per frame in cycles"
        return self.__track.cycles.withdata({"cid": self.cid})

    @property
    def phase(self) -> np.ndarray:
        "return the phases per frame"
        arr = np.zeros(self.__track.nframes, dtype = 'i1')
        nph = self.__track.nphases
        for i, j  in enumerate(np.split(
                arr,
                self.__track.phases.ravel()-self.__track.phases[0,0]
        )[1:]):
            j[:] = i % nph
        return arr

    @property
    def phasecycles(self) -> Cycles:
        "return the phases per frame in cycles"
        return self.__track.cycles.withdata({"phase": self.phase})

    @property
    def zmagcycles(self) -> Cycles:
        "the magnet altitude sampled at frame rate"
        return self.__track.cycles.withdata({"zmag": self.zmag})

    @property
    def cycles(self) -> Cycles:
        "return zmag, phase and cid per cycle"
        return self.__track.cycles.withdata({
            i: getattr(self, i) for i in ('cid', 'zmag', 'phase')
        })

    def keys(self):
        "return the available secondaries"
        return set(self.data.keys()) | {"tservo", "tsample", "tsink", "vcap", "seconds", "zmag"}

    def __getitem__(self, name):
        "returns a secondary value"
        if hasattr(self, name):
            return getattr(self, name)

        return self.__value(name) if name.startswith("T") else self.data[name]

    def __value(self, name):
        val = getattr(self.__track, '_secondaries')
        if val is None or name not in val:
            return None
        arr           = np.copy(val[name])
        arr['index'] -= self.__track.phases[0,0]
        arr           = arr[arr['index'] >= 0]
        arr           = arr[arr['index'] < self.__track.nframes]
        return arr

class LazyProperty:
    "Checks whether the file was opened prior to returning a value"
    LIST: List[str] = []

    def __init__(self, name: str = '', tpe: type = None) -> None:
        self._name = ''
        self._type = tpe
        if tpe and getattr(tpe, '__doc__', None):
            self.__doc__ = tpe.__doc__
        if name:
            self._name = '_'+name
            self.LIST.append(self._name)

    def __set_name__(self, _, name):
        self.__init__(name, self._type)

    @staticmethod
    def _load(inst):
        inst.load()

    def __get__(self, inst: 'Track', owner):
        if inst is not None:
            self._load(inst)

        return (self._type(inst) if self._type and inst else
                getattr(owner if inst is None else inst, self._name))

    def __set__(self, obj: 'Track', val):
        self._load(obj)
        setattr(obj, self._name, val)
        return getattr(obj, self._name)

class InstrumentProperty(LazyProperty):
    "Checks whether the file was opened prior to returning a value"
    def _load(self, inst):
        if not inst.isloaded:
            info = instrumentinfo(inst)
            info['type'] = InstrumentType(info['type'])
            setattr(inst, self._name, info)

class ResettingProperty:
    "Resets all if this attribute is changed"
    def __init__(self):
        self._name = ''

    def __set_name__(self, _, name):
        self._name = '_'+name

    def __get__(self, obj: 'Track', _):
        return getattr(obj, self._name) if obj else self

    def __set__(self, obj: 'Track', val):
        setattr(obj, self._name, val)
        obj.unload()
        return getattr(obj, self._name)

class ViewDescriptor:
    "Access to views"
    tpe:  Optional[type] = None
    args: Dict[str, Any] = dict()

    def __get__(self, instance, owner):
        return self if instance is None else instance.view(self.tpe, **self.args)

    def __set_name__(self, _, name):
        self.tpe  = Cycles if name.startswith('cycles') else Beads
        self.args = dict(copy = False)
        setattr(self, '__doc__', getattr(self.tpe, '__doc__', None))

class PhaseManipulator:
    """
    Helper class for manipulating phases.
    """
    def __init__(self, track):
        self._track = track

    def __getitem__(self, value):
        return PHASE[value]

    def cut(self, cid:PIDTYPE = None) -> Tuple[np.ndarray, np.ndarray]:
        """
        Returns a selection of phases, *reindexed* to zero, with a list of
        frame ids corresponding to theses phases.

        This can be used to create a track containing a fraction of the original data.
        """
        trk = self._track
        if isellipsis(cid):
            cycs = slice(None, None)

        if isinstance(cid, (slice, range)):
            cycs = slice(0               if cid.start is None else cid.start,
                         len(trk.phases) if cid.stop  is None else cid.stop,
                         1               if cid.step  is None else cid.step)
        else:
            cycs = np.array(cid, dtype = 'i4')

        phases = trk.phases[cycs]
        first  = phases[:,0]
        if isinstance(cycs, slice):
            last = trk.phases[cycs.start+1:cycs.stop+1:cycs.step,0]  # type: ignore
        else:
            tmp  = cycs+1
            last = trk.phases[tmp[tmp < len(trk.phases)],0]
        if len(last) < len(first):
            last = np.append(last, trk.nframes+trk.phases[0,0])

        inds   = np.concatenate([np.arange(j, dtype = 'i4')+i for i, j in zip(first, last-first)])
        inds  -= self._track.phases[0, 0]
        phases = (np.insert(np.cumsum(np.diff(np.hstack([phases, last[:,None]]))), 0, 0)
                  [:-1].reshape((-1, phases.shape[1])))
        return inds, phases

    def duration(self, cid:PIDTYPE = None, pid:IDTYPE = None) -> Union[np.ndarray, int]:
        """
        Returns the duration of a phase per cycle.
        """
        if isinstance(pid, (tuple, list, np.ndarray)):
            return np.vstack([self.__duration(cid, i) for i in cast(list, pid)]).T
        return self.__duration(cid, pid)

    def select(self, cid:PIDTYPE = None, pid:PIDTYPE = None) -> Union[np.ndarray, int]:
        """
        Returns the start time of the cycle and phase.

        If pid >= nphases, the end time of cycles is returned.
        if pid is a sequence of ints, a table is returned.
        """
        if isinstance(pid, (tuple, list, np.ndarray)):
            return np.vstack([self.__select(cid, i) for i in cast(list, pid)]).T
        return self.__select(cid, pid)

    nframes  = cast(int, property(lambda self: self._track.nframes))
    ncycles  = cast(int, property(lambda self: self._track.ncycles))
    nphases  = cast(int, property(lambda self: self._track.nphases))
    if __doc__:
        __doc__ += "   * `cut`: "      + cast(str, cut.__doc__)     .strip()+"\n"
        __doc__ += "   * `duration`: " + cast(str, duration.__doc__).strip()+"\n"
        __doc__ += "   * `select`: "   + cast(str, select.__doc__)  .strip()+"\n"

    def __duration(self, cid:PIDTYPE = None, pid:IDTYPE = None) -> Union[np.ndarray, int]:
        phases = self._track.phases
        if isinstance(pid, str):
            pid = self[pid]

        if isinstance(pid, int):
            pid  = range(pid, cast(int, None if pid == -1 else pid+1))
        elif isellipsis(pid):
            pid  = range(phases.shape[1])
        elif isinstance(pid, (slice, range)):
            pid = range(
                None if pid.start is None else self[pid.start],
                None if pid.stop  is None else self[pid.stop]
            )
        else:
            raise TypeError()

        start = 0 if pid.start is None else pid.start
        if pid.stop == start:
            return np.zeros(len(phases), dtype = 'i4')[cid]
        return self.select(cid, pid.stop) - self.select(cid, pid.start)

    def __select(self, cid:PIDTYPE = None, pid:PIDTYPE = None) -> Union[np.ndarray, int]:
        phases = self._track.phases
        ells   = isellipsis(cid), isellipsis(pid)
        if not ells[1]:
            pid = self[pid]
        if np.isscalar(pid) and pid >= self._track.nphases:
            if np.isscalar(cid):
                return (self._track.nframes if cid >= self._track.ncycles-1 else
                        phases[1+cast(int, cid),0]-phases[0,0])

            tmp = np.append(phases[1:,0]-phases[0,0], np.int32(self._track.nframes))
            return tmp[None if ells[0] else cid]

        return (phases        if all(ells) else
                phases[:,pid] if ells[0]   else
                phases[cid,:] if ells[1]   else
                phases[cid,pid]) - phases[0,0]

class PathInfo:
    """
    Provides information on the path itself:

    * `paths`: a tuple of paths
    * `trackpath`: the main path, i.e. not the grs
    * `size` (*megabytes*) is the size in bytes (megabytes) of *trackpath*
    * `stat`: stats on the *trackpath*
    * `modification`: the date oflast modification. This is basically the
    time of experiment.
    * `creation`: the creation date. **DISCARD** when using PicoTwist tracks.
    """
    track: 'Track'

    def __get__(self, inst, tpe):
        if inst is None:
            return self
        cpy       = PathInfo()
        cpy.track = inst
        return cpy

    @property
    def paths(self) -> List[Path]:
        "returns all paths"
        path = self.track.path
        return (
            [Path(path)] if isinstance(path, str)  else
            [path]       if isinstance(path, Path) else
            []           if path is None           else
            [Path(str(i)) for i in cast(Iterable, path)]
        )

    @property
    def trackpath(self) -> Path:
        "returns all paths"
        path = self.track.path
        return Path(str(path[0])) if isinstance(path, (list, tuple)) else Path(str(path))

    pathcount    = property(lambda self: len(self.paths))
    stat         = property(lambda self: self.trackpath.stat())
    size         = property(lambda self: self.stat.st_size)
    megabytes    = property(lambda self: self.size >> 20)
    creation     = property(lambda self: datetime.fromtimestamp(self.stat.st_ctime))

    @property
    def modification(self):
        "return the modification date of the **original** track file."
        date = getattr(self.track, '_modificationdate', None)
        if date is None and self.trackpath.exists():
            date = self.stat.st_mtime
        else:
            date = 0
        return datetime.fromtimestamp(date)

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
    * `phases` is a 2D array with one row per cycle and one column per phase
    containing the first index value of each cycle and phase.
    * `path` is the path(s) to the data
    * `axis` (Є {{'X', 'Y', 'Z'}}) is the data axis
    * `ncycles` is the number of cycles
    * `nphases` is the number of phases
    * `secondaries` {secondaries}
    * `fov` {fov}
    * `pathinfo` {pathinfo}
    """
    if __doc__:
        __doc__ = __doc__.format(
            secondaries = _doc(Secondaries),
            fov         = _doc(FoV),
            pathinfo    = _doc(PathInfo)
        )

    key: Optional[str] = None
    instrument         = cast(Dict[str, Any],      InstrumentProperty())
    phases             = cast(np.ndarray,          LazyProperty())
    framerate          = cast(float,               LazyProperty())
    fov                = cast(FoV,                 LazyProperty())
    secondaries        = cast(Secondaries,         LazyProperty(tpe = Secondaries))
    path               = cast(Optional[PATHTYPES], ResettingProperty())
    axis               = cast(Axis,                ResettingProperty())
    data               = cast(
        DATA,
        property(lambda self: self.getdata(), lambda self, val: self.setdata(val))
    )

    @initdefaults('key',
                  **{i: '_' for i in locals() if i != 'key' and i[0] != '_'})
    def __init__(self, **kwa):
        self._rawprecisions: _RawPrecisionCache = _RawPrecisionCache()
        if 'rawprecisions' in kwa and isinstance(kwa['rawprecisions'], _RawPrecisionCache):
            self._rawprecisions = kwa['rawprecisions']
        elif 'rawprecisions' in kwa:
            self._rawprecisions.computer = kwa['rawprecisions']

    ncycles  = cast(int,                 property(lambda self: len(self.phases)))
    nphases  = cast(int,                 property(lambda self: self.phases.shape[1]))
    beads    = cast(Beads,               ViewDescriptor())
    cycles   = cast(Cycles,              ViewDescriptor())
    phase    = property(PhaseManipulator, doc = PhaseManipulator.__doc__)
    pathinfo = PathInfo()

    def getdata(self) -> DATA:
        "returns the dataframe with all bead info"
        self.load()
        return cast(DATA, self._data)

    def setdata(self, data: Optional[Dict[int, np.ndarray]]):
        "sets the dataframe"
        if data is None:
            self.unload()
        else:
            self._data = data

    @property
    def nframes(self) -> int:
        "returns the number of frames"
        return len(next(iter(self.data.values()), []))

    @property
    def isloaded(self) -> bool:
        "returns whether the data was already acccessed"
        return self._data is not None

    def load(self, cycles: Optional[slice] = None) -> 'Track':
        "Loads the data"
        if self._data is None and self._path is not None:
            opentrack(self, cycles)
        return self

    def unload(self):
        "Unloads the data"
        for name in _lazies():
            setattr(self, name, deepcopy(getattr(type(self), name)))

    def view(self, tpe:Union[Type[TrackView], str], **kwa):
        "Creates a view of the suggested type"
        viewtype = (tpe     if isinstance(tpe, type) else
                    Cycles  if tpe.lower() == 'cycles' else
                    Beads)
        kwa.setdefault('parents', (self.key,) if self.key else (self.path,))
        kwa.setdefault('track',   self)
        return viewtype(**kwa)

    @overload       # noqa: F811
    def rawprecision(
            self,
            ibead:  int,
            phases: Union[None, Dict[int, float], Tuple[int, int]],
    ):
        "Obtain the raw precision for a given bead"

    @overload       # noqa: F811
    def rawprecision(self, computertype: str) -> None:
        "Set the raw precision computer"

    @overload       # noqa: F811
    def rawprecision(self) -> str:
        "Obtain the raw precision computer"

    @overload       # noqa: F811
    def rawprecision(
            self,
            ibead:  Optional[Iterable[int]],
            phases: Union[None, Dict[int, float], Tuple[int, int]],
    ) -> Iterator[Tuple[int,float]]:
        "Obtain the raw precision for a number of beads"

    def rawprecision(self, ibead = NoArgs, phases = None):   # noqa: F811
        "Obtain the raw precision for a number of beads"
        if ibead is NoArgs:
            return self._rawprecisions.computer
        if isinstance(ibead, (type, str)):
            self._rawprecisions.computer = ibead
            return None
        return self._rawprecisions.get(self, ibead, phases)

    if __doc__ is not None:
        setattr(rawprecision, '__doc__', getattr(_RawPrecisionCache.get, '__doc__', None))

    beadextension = _beadextension
    phaseposition = _phaseposition

    def shallowcopy(self):
        "make a shallow copy of the track: different containers but for the true data"
        cpy = self.__class__()
        cpy.__dict__.update({i: copy(j) for i, j in self.__dict__.items()})
        return cpy

    def __getstate__(self):
        keys = set(_lazies()+('_path', '_axis'))

        test = dict.fromkeys(keys, lambda i, j: j != getattr(type(self), i))  # type: ignore
        test.update(_phases = lambda _, i: len(i),
                    key     = lambda _, i: i is not None)

        cnv  = dict.fromkeys(keys | {'key'}, lambda i: i)  # type: ignore
        cnv.update(_secondaries = lambda i: getattr(i, 'data', None),
                   _axis        = lambda i: getattr(i, 'value', i)[0])

        info = self.__dict__.copy()
        if self._lazydata_:
            for i in ('_data', '_secondaries', '_fov'):
                info.pop(i, None)

        for name in set(cnv) & set(info):
            val = info.pop(name)
            if test[name](name, val):
                info[name[1:] if name[0] == '_' else name] = cnv[name](val)
        return info

    def __setstate__(self, values):
        if isinstance(values.get('fov', None), dict):
            fov           = values['fov']
            fov["beads"]  = {i: Bead(**j) for i, j in fov.get('beads', {}).items()}
            values['fov'] = FoV(**fov)

        if isinstance(values.get('instrument', {}).get("type", None), str):
            values['instrument']['type'] = InstrumentType(values['instrument']['type'])

        self.__init__(**values)
        keys = frozenset(self.__getstate__().keys()) | frozenset(('data', 'secondaries'))
        self.__dict__.update({i: j for i, j in values.items() if i not in keys})

    @property
    def _lazydata_(self):
        """
        Used internally to discard the data from __getstate__, or not
        """
        return self.__dict__.get('_lazydata_', self.path is not None)

    @_lazydata_.setter
    def _lazydata_(self, val):
        if val is None:
            self.__dict__.pop('_lazydata_', None)
        else:
            self.__dict__['_lazydata_'] = val

    _framerate:       float                = 30.
    _fov:             Optional[FoV]        = None
    _instrument:      Dict[str, Any]       = {
        "type": InstrumentType.picotwist.name,
        "name": None
    }
    _phases:          np.ndarray           = np.empty((0,9), dtype = 'i4')
    _data:            Optional[DATA]       = None  # type: ignore
    _secondaries:     Optional[DATA]       = None
    _rawprecisions:   _RawPrecisionCache   = _RawPrecisionCache()
    _path:            Optional[PATHTYPES]  = None
    _axis:            Axis                 = Axis.Zaxis
