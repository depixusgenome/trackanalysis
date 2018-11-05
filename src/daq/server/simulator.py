#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Simulate the server"
import socket
import struct
import time
from   abc              import ABC, abstractmethod
from   multiprocessing  import Process, Value
from   typing           import Union, Optional, Tuple

import numpy        as     np

from   daq.model        import DAQClient
from   utils            import initdefaults
from   utils.logconfig  import getLogger

LOGS = getLogger(__name__)

def writedaq(nbeads: int,  # pylint: disable=too-many-locals,too-many-arguments
             cnf: DAQClient, period, output = None, state = None, kwa = None):
    """
    Reads server data and outputs it
    """
    while state is None or state.value != 0:
        if output is None:
            output = 300

        LOGS.info("output: %s", output)
        tmp    = np.sin(np.arange(output, dtype = 'f4')/output*6*np.pi)
        dtype  = cnf.dtype(nbeads)
        vals   = [(np.roll(tmp*(i+1), i*10) if k == '<f4' else
                   np.arange(len(tmp), dtype = k))
                  for i, (j, k) in enumerate(dtype.descr)]
        data   = np.array([tuple(vals[j][i] for j in range(len(vals)))
                           for i in range(output)], dtype = dtype)
        if 'ttype' in dtype.names:
            data['ttype'][::3]  = (1 << 0) + (1<<3) + (1<<6)
            data['ttype'][1::3] = (1 << 1) + (1<<4) + (1<<7)
            data['ttype'][2::3] = (1 << 2) + (1<<5)

        addr   = (cnf.multicast, cnf.address[1])
        if kwa:
            for i, j in kwa.items():
                if j.value >= 0:
                    LOGS.info("Running simulator on %s %s=%s", addr, i, j)
                    data[i][:] = j.value

        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, struct.pack('b', 1))
            LOGS.info("Running simulator on %s T=%s S=%s N=%s",
                      addr, period, data.dtype.itemsize, nbeads)
            cur = None if state is None else state.value
            for line in data:
                if state is not None and state.value != cur:
                    nbeads = state.value
                    break
                sock.sendto(line.tobytes(), addr)
                time.sleep(period)

    LOGS.info("Stopping simulator on %s T=%s S=%s", addr, period, state.value)

def _runsimulator(nbeads: int, # pylint: disable=too-many-arguments
                  cnf: DAQClient,
                  period: float                  = 1/30.,
                  output: Union[int, np.ndarray] = None,
                  subprocess: bool               = True,
                  state                          = None,
                  kwa                            = None) -> Optional[Tuple[Process, Value]]:
    "run the simulator"
    if subprocess:
        state = Value('i', 1)
        proc  = Process(target = _runsimulator, args = (nbeads, cnf, period, output,
                                                        False, state, kwa))
        return proc, state

    writedaq(nbeads, cnf, period, output, state, kwa)
    return None

def runbeadssimulator(nbeads: int,
                      cnf: DAQClient                 = None,
                      output: Union[int, np.ndarray] = None,
                      period                         = 1./30.,
                      subprocess: bool               = True
                     ) -> Optional[Tuple[Process, Value]]:
    "run the simulator"
    return _runsimulator(max(0, nbeads), cnf, period, output, subprocess)

def runfovsimulator(cnf: DAQClient                 = None,
                    output: Union[int, np.ndarray] = None,
                    period                         = 1./30.,
                    subprocess: bool               = True,
                    **kwa
                   ) -> Optional[Tuple[Process, Value]]:
    "run the simulator"
    return _runsimulator(-1, cnf, period, output, subprocess, kwa = kwa)

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

        @ctrl.daq.observe
        def _onlisten(old = None, **_):
            if f"{self._NAME}started" in old:
                self._start(ctrl)

        @ctrl.display.observe
        def _onguiloaded(**_):
            ctrl.daq.listen(**{self._NAME: self._nbeads(ctrl) != 0})
        return False

    @staticmethod
    def addtodoc(*_):
        "nothing to do"
        return

    def _run(self, nbeads, ctrl, **kwa):
        self._proc, self._state = _runsimulator(nbeads,
                                                getattr(ctrl.daq.config.network,
                                                        self._NAME),
                                                period     = self._model.period,
                                                output     = self._model.output,
                                                subprocess = True,
                                                kwa        = kwa)

    def _start(self, ctrl, **_):
        nbeads = self._nbeads(ctrl)
        if getattr(ctrl.daq.data, f'{self._NAME}started') and nbeads != 0:
            if self._proc:
                if nbeads > 0:
                    self._state.value = nbeads
                return

            self._run(nbeads, ctrl)
            LOGS.info("Simulator %s in another process", self._NAME)
            self._proc.start()

        elif self._proc:
            self._state.value = 0
            self._proc        = None
            return

    def close(self):
        "stop simulating the daq"
        if self._proc:
            self._state.value = 0
            self._proc        = None

    @staticmethod
    @abstractmethod
    def _nbeads(ctrl) -> int:
        pass

class DAQFoVServerSimulatorView(BaseServerSimulatorView):
    """
    view for simulating the server
    """
    _NAME = "fov"
    def __init__(self, **_):
        self._cycles = Value('i', -1)
        super().__init__(**_)

    @staticmethod
    def _nbeads(_) -> int:
        return -1

    def _run(self, nbeads, ctrl, **_):
        self._cycles = Value('i', 0 if ctrl.daq.config.protocol.ismanual() else -1)
        super()._run(nbeads, ctrl, cycle = self._cycles)

    def observe(self, ctrl):
        "observe the controller"
        if super().observe(ctrl):
            return

        @ctrl.daq.observe
        def _onupdateprotocol(**_):
            self._cycles.value = 0 if ctrl.daq.config.protocol.ismanual() else -1
            self._state.value += 1

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
            if not ctrl.daq.data.beadsstarted:
                ctrl.daq.listen(beads = True)
            else:
                self._start(ctrl)

        @ctrl.daq.observe
        def _onremovebeads(**_):
            nbeads = len(ctrl.daq.config.beads) > 0
            if ctrl.daq.data.beadsstarted != nbeads:
                ctrl.daq.listen(beads = nbeads)
            else:
                self._start(ctrl)
