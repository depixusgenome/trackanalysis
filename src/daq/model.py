#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"DAQ Model"
from   collections          import ChainMap
from   typing               import Optional, Tuple, Union, List, cast
import numpy                as     np
from   utils                import initdefaults

class ColDescriptor:
    "easy creation of np.dtype"
    def __init__(self, val: Union[np.dtype, List[Tuple[str, str]]]) -> None:
        self.defaults = np.dtype(val)

    def __get__(self, inst, owner) -> np.dtype:
        return  self.defaults if inst is None else inst.__dict__['columns']

    def __set__(self, inst, val: Union[np.dtype, List[Tuple[str, str]]]):
        inst.__dict__['columns'] = np.dtype(val)

class DAQClient:
    """
    All information related to the current protocol
    """
    multicast = '239.255.0.1'
    period    = 30 # milliseconds
    address   = ('', 30001)
    bytesize  = 64
    offset    = 4
    packet    = 3
    columns   = cast(np.dtype, ColDescriptor([("time",    'i8'),
                                              ("zmag",    'f4'),
                                              ("vmag",    'f4'),
                                              ("zobj",    'f4'),
                                              ("x",       'f4'),
                                              ("y",       'f4'),
                                              ("tsample", 'f4'),
                                              ("tmagnet", 'f4'),
                                              ("tsink",   'f4'),
                                              ("led1",    'f4'),
                                              ("led2",    'f4')]))
    @initdefaults(frozenset(locals()))
    def __init__(self, **kwa):
        pass

class DAQNetwork:
    """
    All information related to the current protocol
    """
    camera:    str = "rtsp://jupyter.depixus.org:9099"
    websocket: str = "ws://jupyter.depixus.org:9099"
    fov            = DAQClient()
    beads          = DAQClient(columns = [('time', 'i8'), *((i, 'f4') for i in 'xyz')])
    @initdefaults(frozenset(locals()))
    def __init__(self, **kwa):
        pass

    @property
    def config(self):
        "return a chainmap with default and updated values"
        get  = lambda i: getattr(i, '__dict__', i)
        cur  = {i: get(j)                          for i, j in self.__dict__.items()}
        dflt = {i: get(getattr(self.__class__, i)) for i in self.__dict__}
        return ChainMap({i: j for i, j in cur.items() if j != dflt[i]}, dflt)

class DAQPhase:
    """
    All information related to one phase in a cycle
    """
    duration: int   = None # in frames
    zmag:     float = None # requested zmag position at end of phase (in µm)
    speed:    float = None

    @initdefaults(frozenset(locals()))
    def __init__(self, **kwa):
        pass

    def __cmp__(self, other):
        return self.__class__ is other.__class__ and self.__dict__ == other.__dict__

class DAQProtocol:
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

    def __cmp__(self, other):
        return self.__class__ is other.__class__ and self.__dict__ == other.__dict__

class DAQIdle(DAQProtocol):
    """
    Idle status
    """
    def __init__(self, **kwa):
        self.__dict__['phases'] = (DAQPhase(zmag = 10., duration = None),)
        self.zmag = kwa.get('zmag', self.zmag)
        super().__init__(**kwa)

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
    phases: Tuple[DAQPhase,...] = (DAQPhase(zmag     = 10.),
                                   DAQPhase(duration = 20),
                                   DAQPhase(zmag     = 18),
                                   DAQPhase(duration = 20),
                                   DAQPhase(zmag     = 10, speed = .1),
                                   DAQPhase(duration = 400),
                                   DAQPhase(zmag     = 5.),
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

class DAQRecording:
    "everything for recording the data"
    path: str     = None
    started       = False
    duration: int = None
    @initdefaults(frozenset(locals()))
    def __init__(self, **kwa):
        pass

class DAQDataConfig:
    """
    All global information related to a set of data
    """
    columns   = ["x", "y", "z"]
    maxlength = 5000
    @initdefaults(frozenset(locals()))
    def __init__(self, **kwa):
        pass

class DAQBead:
    """
    All global information related to a bead
    """
    roi = (0, 0, 100, 100)
    @initdefaults(frozenset(locals()))
    def __init__(self, **kwa):
        pass

class DAQConfig:
    """
    All information related to the current status
    """
    network                       = DAQNetwork()
    protocol: DAQProtocol         = DAQIdle()
    beads :   Tuple[DAQBead, ...] = ()

    fovdata     = DAQDataConfig(columns = network.fov.columns,  maxlength = 60000)
    beaddata    = DAQDataConfig(columns = np.dtype("f4,f4,f4"), maxlength = 60000)
    defaultbead = DAQBead()
    recording   = DAQRecording()

    @initdefaults(frozenset(locals()))
    def __init__(self, **kwa):
        pass
