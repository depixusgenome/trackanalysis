#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"DAQ Model"
from   collections          import ChainMap
from   typing               import (Optional, Tuple, Union, Dict, Any, List,
                                    Iterable, ClassVar, cast)
import numpy                as     np
from   utils                import initdefaults
from   utils.inspection     import diffobj

class ConfigObject:
    """
    Object with a few helper function for comparison
    """
    def __eq__(self, other):
        return isinstance(other, self.__class__) and self.__dict__ == other.__dict__

    def diff(self, other) -> Dict[str, Any]:
        "return the diff with `other`"
        return diffobj(self, other)

    def config(self, tpe = dict):
        "return a chainmap with default and updated values"
        if tpe in (dict, 'dict'):
            return dict(self.__dict__)

        get  = lambda i: getattr(i, '__dict__', i)
        cur  = {i: get(j)                          for i, j in self.__dict__.items()}
        dflt = {i: get(getattr(self.__class__, i)) for i in self.__dict__}
        return ChainMap({i: j for i, j in cur.items() if j != dflt[i]}, dflt)

FOVTYPE  = [('msg',  'B'),      ('err',     'uint16'), ('ttype',    'B'),
            ('time', 'uint64'), ('zstatus', 'B'),      ('xystatus', 'B'),
            ('zmag', 'f4'),     ('vmag',    'f4'),     ('zobj',    'f4'),
            ('x',    'f4'),     ('y',       'f4'),     ('t1',      'f4'),
            ('t2',   'f4'),     ('t3',      'f4'),     ('led1',    'f4'),
            ('led2', 'f4'),     ('phase',   'uint32'), ('cycle',   'uint32'),
            ('_r0',  'uint32'), ('_r1',     'uint16')]

BEADTYPE = [('time', 'uint32'),  ("x", 'f4'), ("y", 'f4'), ("z", 'f4')]

class ColDescriptor:
    "easy creation of np.dtype"
    def __init__(self, val: Union[np.dtype, List[Tuple[str, str]]]) -> None:
        self.defaults = np.dtype(val)

    def __get__(self, inst, owner) -> np.dtype:
        return  self.defaults if inst is None else inst.__dict__['columns']

    def __set__(self, inst, val: Union[np.dtype, List[Tuple[str, str]]]):
        inst.__dict__['columns'] = np.dtype(val)

class DAQClient(ConfigObject):
    """
    All information related to the current protocol
    """
    multicast    = '239.255.0.1'
    address      = ('', 30001)
    columns      = cast(np.dtype, ColDescriptor(FOVTYPE))
    @initdefaults(frozenset(locals()))
    def __init__(self, **kwa):
        pass

    def dtype(self, *_) -> np.dtype:
        "create the dtype for the whole data"
        return self.columns

class TemperatureStatus:
    """
    Deals with the fact that temperatures are stored in the same fov data field
    """
    flags = {'tbox':    1<<0, 'tsample': 1<<1, 'tmagnet':  1<<2,
             'ttresse': 1<<3, 'tsink':   1<<4, 'tmagsink': 1<<5,
             'tair':    1<<6, 'rh':      1<<7}
    field = {'tbox':    't1', 'tsample': 't1',
             'tmagnet': 't2', 'ttresse': 't2',
             'tsink':   't3', 'tmagsink': 't3', 'tair': 't3', 'rh': 't3'}
    state = 'ttype'
    @initdefaults(frozenset(locals()))
    def __init__(self,**_):
        pass

    @property
    def names(self):
        "return the names of the temperatures"
        return iter(self.flags)

    def indexes(self, name, lines) -> Union[np.ndarray, slice]:
        "return an array of booleans indicating which index is good"
        flag = self.flags.get(name, None)
        if flag is None:
            return slice(None, None)
        return np.bitwise_and(lines[self.state], self.flags[name]) != 0

    def data   (self, name, lines) -> np.ndarray:
        "return an array of booleans indicating which index is good"
        return lines[self.field[name]][self.indexes(name, lines)]

class DAQFoVClient(DAQClient):
    """
    All information related to the current protocol
    """
    columns      = cast(np.dtype, ColDescriptor(FOVTYPE))
    address      = ('', 30001)
    multicast    = '239.255.0.1'
    temperatures = TemperatureStatus()

    @initdefaults("temperatures")
    def __init__(self, **kwa):
        super().__init__(**kwa)

class DAQBeadsClient(DAQClient):
    """
    All information related to the current protocol
    """
    columns   = cast(np.dtype, ColDescriptor(BEADTYPE))
    address   = ('', 30002)
    multicast = '239.255.0.2'
    def dtype(self, nbeads:int) -> np.dtype: # type: ignore # pylint: disable=arguments-differ
        "create the dtype for all beads"
        cols = self.columns.descr[:1]
        for i in range(nbeads):
            cols += [(j+str(i), k) for j, k in self.columns.descr[1:]]
        return np.dtype(cols)

class DAQCamera(ConfigObject):
    """
    camera information: address & pixel size
    """
    address = "rtsp://192.168.1.56:8554/mystream"
    pixels  = 1936, 1216
    dim     = (0.08368080109357834, 0), (0.08368080109357834, 0)

    def bounds(self, pixel = False):
        "image bounds in nm (*pixel == False*) or pixels"
        rng = self.pixels[0], self.pixels[1]
        return (0, 0) + rng if pixel else self.tonm((0,0))+ self.tonm(rng)

    def size(self, pixel = False):
        "image size in nm (*pixel == False*) or pixels"
        rng = self.pixels[0], self.pixels[1]
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

class DAQNetwork(ConfigObject):
    """
    All information related to the current protocol
    """
    camera    = DAQCamera()
    websocket = "ws://jupyter.depixus.org:9099"
    fov       = DAQFoVClient()
    beads     = DAQBeadsClient()

    @initdefaults(frozenset(locals()))
    def __init__(self, **kwa):
        pass

class DAQPhase(ConfigObject):
    """
    All information related to one phase in a cycle
    """
    duration: int   = None # in frames
    zmag:     float = None # requested zmag position at end of phase (in µm)
    speed:    float = None

    @initdefaults(frozenset(locals()))
    def __init__(self, **kwa):
        pass

class DAQProtocol(ConfigObject):
    """
    All information related to the current protocol
    """
    name: ClassVar[str]          = ""
    framerate                    = 30
    cyclecount                   = 120
    phases: Tuple[DAQPhase, ...] = ()
    @initdefaults(frozenset(locals()) - {'cyclecount', 'phases', 'name'})
    def __init__(self, **kwa):
        pass

    def __eq__(self, other):
        return isinstance(other, self.__class__) and self.__dict__ == other.__dict__

    @classmethod
    def ismanual(cls):
        "return whether this protocol is manual"
        return cls.name == 'daqmanual'

class DAQManual(DAQProtocol):
    """
    Manual status
    """
    name: ClassVar[str] = "daqmanual"
    def __init__(self, **kwa):
        self.__dict__['phases'] = (DAQPhase(zmag = 10., duration = None, speed = 1.),)
        self.zmag  = kwa.pop('zmag',  self.zmag)
        self.speed = kwa.pop('speed', self.speed)
        super().__init__(**kwa)

    @property
    def speed(self) -> float:
        "return the requested speed"
        return self.__dict__['phases'][0].speed

    @speed.setter
    def speed(self, value: float):
        "set the requested speed"
        self.__dict__['phases'][0].speed = value

    @property
    def zmag(self) -> float:
        "return the requested zmag"
        return self.__dict__['phases'][0].zmag

    @zmag.setter
    def zmag(self, value: float):
        "set the requested zmag"
        self.__dict__['phases'][0].zmag = value

    # make attributes readonly
    phases      = cast(Tuple[DAQPhase, ...], property(lambda self: self.__dict__['phases']))
    cyclecount  = cast(Optional[int],        property(lambda _: None))

class DAQProbe(DAQProtocol):
    """
    Probe status
    """
    name  : ClassVar[str]       = "daqprobe"
    phases: Tuple[DAQPhase,...] = (DAQPhase(zmag     = 10., speed = 1.),
                                   DAQPhase(duration = 20),
                                   DAQPhase(zmag     = 18,  speed = .125),
                                   DAQPhase(duration = 20),
                                   DAQPhase(zmag     = 10,  speed = .125),
                                   DAQPhase(duration = 400),
                                   DAQPhase(zmag     = 5.,  speed = 1.),
                                   DAQPhase(duration = 20))
    cyclecount                  = 120
    probes: Tuple[str,...]      = ()
    @initdefaults(frozenset(locals())-{'name'})
    def __init__(self, **kwa):
        super().__init__(**kwa)

class DAQRamp(DAQProbe):
    """
    Ramp status
    """
    name  : ClassVar[str]       = "daqramp"
    phases: Tuple[DAQPhase,...] = (DAQPhase(zmag     = 20., speed  = .1),
                                   DAQPhase(duration = 30),
                                   DAQPhase(zmag     = 10., speed  = .1))
    cyclecount                  = 30

class DAQRecording(ConfigObject):
    "everything for recording the data"
    path: str     = None
    started       = False
    @initdefaults(frozenset(locals()))
    def __init__(self, **kwa):
        pass

class DAQBead(ConfigObject):
    """
    All global information related to a bead
    """
    roi = (0, 0, 100, 100)
    @initdefaults(frozenset(locals()))
    def __init__(self, **kwa):
        pass

    @staticmethod
    def toarray(beads: Iterable['DAQBead']) -> np.ndarray:
        "returns all beads in the shape of an array"
        return np.array([tuple(i.roi) for i in beads],
                        dtype = [('x', 'f4'), ('y', 'f4'),
                                 ('w', 'f4'), ('h', 'f4')])

    @classmethod
    def todict(cls, beads: Iterable['DAQBead']) -> Dict[str, np.ndarray]:
        "returns all beads in the shape of an array"
        roi = cls.toarray(beads)
        return {i: roi[i] for i in roi.dtype.names}

class DAQConfig(ConfigObject):
    """
    All information related to the current status
    """
    network                       = DAQNetwork()
    protocol: DAQProtocol         = DAQManual()
    beads :   Tuple[DAQBead, ...] = ()

    defaultbead = DAQBead()
    recording   = DAQRecording()

    @initdefaults(frozenset(locals()))
    def __init__(self, **kwa):
        pass
