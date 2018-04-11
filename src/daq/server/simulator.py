#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Simulate the server"
import asyncio
import socket
import struct
from   abc              import ABC, abstractmethod
from   functools        import partial
from   multiprocessing  import Process, Value
from   typing           import Union, Optional, Tuple

import numpy        as     np

from   daq.model        import DAQClient
from   utils            import initdefaults
from   utils.logconfig  import getLogger

LOGS = getLogger(__name__)

async def writedaq(nbeads: int, cnf: DAQClient, period, output = None, state = None):
    """
    Reads server data and outputs it
    """
    if output is None:
        output = 300

    if np.isscalar(output):
        tmp    = np.sin(np.arange(output, dtype = 'f4')/output*6*np.pi)
        dtype  = cnf.fovtype() if nbeads < 0 else cnf.beadstype(nbeads)
        vals   = [np.empty(output, dtype = 'f4')  if j == '_' else
                  np.arange(output, dtype = 'i8') if k.endswith('i8') else
                  np.roll(tmp*(i+1), i*10) for i, (j, k) in enumerate(dtype.descr)]
        output = np.array([tuple(vals[j][i] for j in range(len(vals)))
                           for i in range(output)], dtype = dtype)
    else:
        output = np.asarray(output)

    addr   = (cnf.multicast, cnf.address[1])
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, struct.pack('b', 1))
        LOGS.info("Running simulator on %s T=%s S=%s", addr, period, output.dtype.itemsize)
        while state is None or state.value:
            for data in output:
                sock.sendto(data.tobytes(), addr)
                await asyncio.sleep(period)
    LOGS.info("Stopping simulator on %s T=%s", addr, period)

def _runsimulator(nbeads: int, # pylint: disable=too-many-arguments
                  cnf: DAQClient,
                  period: float                  = 1/30.,
                  output: Union[int, np.ndarray] = None,
                  subprocess: bool               = True,
                  state                          = None) -> Optional[Tuple[Process, Value]]:
    "run the simulator"
    if subprocess:
        state = Value('i', 1)
        proc  = Process(target = _runsimulator, args = (nbeads, cnf, period, output, False, state))
        return proc, state

    policy = asyncio.get_event_loop_policy()
    policy.set_event_loop(policy.new_event_loop())
    loop   = asyncio.get_event_loop()
    loop.run_until_complete(writedaq(nbeads, cnf, period, output, state))
    loop.close()
    return None

def runbeadssimulator(nbeads: int,
                      cnf: DAQClient                 = None,
                      output: Union[int, np.ndarray] = None,
                      subprocess: bool               = True
                     ) -> Optional[Tuple[Process, Value]]:
    "run the simulator"
    return _runsimulator(max(0, nbeads), cnf, output, subprocess)

def runfovsimulator(cnf: DAQClient                 = None,
                    output: Union[int, np.ndarray] = None,
                    subprocess: bool               = True
                   ) -> Optional[Tuple[Process, Value]]:
    "run the simulator"
    return _runsimulator(-1, cnf, output, subprocess)

class DAQSimulator:
    """
    Relative to the amount of raw memory to keep
    """
    name        = "simulator"
    output      = 10000
    period      = 1/30 # seconds
    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        pass

class BaseServerSimulatorView(ABC):
    """
    view for simulating the server
    """
    _NAME = ''
    def __init__(self, **_):
        self._proc:  Process = None
        self._state: Value   = None
        self._model          = DAQSimulator(name = f"{self._NAME}simulator")

    def observe(self, ctrl):
        "observe the controller"
        if self._model in ctrl.theme:
            return True

        ctrl.theme.add(self._model)
        ctrl.daq.observe("listen", partial(self._start,   ctrl))

        @ctrl.display.observe
        def _onguiloaded():
            ctrl.daq.listen(**{self._NAME: self._nbeads(ctrl) != 0})
        return False

    @staticmethod
    def addtodoc(*_):
        "nothing to do"
        return

    def _start(self, ctrl, **_):
        proc, self._proc = self._proc, None
        if proc:
            self._state.value = 0
            self._state       = None
            proc.join()

        nbeads = self._nbeads(ctrl)
        if getattr(ctrl.daq.data, f'{self._NAME}started') and nbeads != 0:
            self._proc, self._state = _runsimulator(nbeads,
                                                    getattr(ctrl.daq.config.network,
                                                            self._NAME),
                                                    period     = self._model.period,
                                                    output     = self._model.output,
                                                    subprocess = True)
            LOGS.info("Simulator %s in another process", self._NAME)
            self._proc.start()

    @staticmethod
    @abstractmethod
    def _nbeads(ctrl) -> int:
        pass

class DAQFoVServerSimulatorView(BaseServerSimulatorView):
    """
    view for simulating the server
    """
    _NAME = "fov"
    @staticmethod
    def _nbeads(_) -> int:
        return -1

class DAQBeadsServerSimulatorView(BaseServerSimulatorView):
    """
    view for simulating the server
    """
    _NAME = "beads"
    @staticmethod
    def _nbeads(ctrl) -> int:
        return len(ctrl.daq.config.beads)

    def observe(self, ctrl):
        "observe the controller"
        if super().observe(ctrl):
            return

        @ctrl.daq.observe
        def _onaddbeads(**_):
            ctrl.daq.listen(beads = True)

        @ctrl.daq.observe
        def _onremovebeads(**_):
            ctrl.daq.listen(beads = len(ctrl.daq.config.beads) > 0)
