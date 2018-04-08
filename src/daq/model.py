#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"DAQ Model"
from   collections          import ChainMap
from   typing               import (Optional, Tuple, Union, Dict, Any, List,
                                    Iterable, cast)
import numpy                as     np
from   utils                import initdefaults
from   utils.inspection     import diffobj

class ColDescriptor:
    "easy creation of np.dtype"
    def __init__(self, val: Union[np.dtype, List[Tuple[str, str]]]) -> None:
        self.defaults = np.dtype(val)

    def __get__(self, inst, owner) -> np.dtype:
        return  self.defaults if inst is None else inst.__dict__['columns']

    def __set__(self, inst, val: Union[np.dtype, List[Tuple[str, str]]]):
        inst.__dict__['columns'] = np.dtype(val)

FOVTYPE  = [("time",  'i8'), ("zmag", 'f4'), ("vmag",    'f4'), ("zobj",    'f4'),
            ("x",     'f4'), ("y",    'f4'), ("tsample", 'f4'), ("tmagnet", 'f4'),
            ("tsink", 'f4'), ("led1", 'f4'), ("led2",    'f4')]

BEADTYPE = [('time', 'i8'),  ("x", 'f4'), ("y", 'f4'), ("z", 'f4')]

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

class DAQClient(ConfigObject):
    """
    All information related to the current protocol
    """
    multicast = '239.255.0.1'
    rate      = 1./3e-2 # milliseconds
    address   = ('', 30001)
    bytesize  = 64
    offset    = 4
    columns   = cast(np.dtype, ColDescriptor(FOVTYPE))
    @initdefaults(frozenset(locals()))
    def __init__(self, **kwa):
        pass

    def fovtype(self) -> np.dtype:
        "create the dtype for all fov data"
        right = self.bytesize-self.offset-self.columns.itemsize
        assert self.offset >= 0 and self.offset % 4 == 0 and right >= 0 and right % 4 == 0
        cols = [*((f"_l{i}", 'i4') for i in range(self.offset//4)),
                *self.columns.descr,
                *((f"_r{i}", 'i4') for i in range(right//4))]
        return np.dtype(cols)

    def beadstype(self, nbeads:int):
        "create the dtype for all beads"
        if self.offset:
            raise NotImplementedError()
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
    fov       = DAQClient(columns = FOVTYPE)
    beads     = DAQClient(columns = BEADTYPE)
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
    framerate                    = 30
    roi                          = None
    cyclecount: int              = None
    phases: Tuple[DAQPhase, ...] = ()
    @initdefaults(frozenset(locals()) - {'cyclecount', 'phases'})
    def __init__(self, **kwa):
        pass

    def __eq__(self, other):
        return isinstance(other, self.__class__) and self.__dict__ == other.__dict__

class DAQManual(DAQProtocol):
    """
    Manual status
    """
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
    @initdefaults(frozenset(locals()))
    def __init__(self, **kwa):
        super().__init__(**kwa)

class DAQRamp(DAQProbe):
    """
    Ramp status
    """
    phases: Tuple[DAQPhase,...] = (DAQPhase(zmag     = 20., speed  = .1),
                                   DAQPhase(duration = 30),
                                   DAQPhase(zmag     = 10., speed  = .1))
    cyclecount                  = 30

class DAQRecording(ConfigObject):
    "everything for recording the data"
    path: str     = None
    started       = False
    duration: int = None
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
