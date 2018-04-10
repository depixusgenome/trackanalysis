#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Simulate the server"
import asyncio
import socket
import struct
from   functools        import partial
from   multiprocessing  import Process
from   typing           import Union, Optional

import numpy        as     np

from   utils.logconfig  import getLogger
from   daq.model        import DAQClient

LOGS = getLogger(__name__)

async def writedaq(nbeads: int, cnf: DAQClient, output = None):
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

    addr   = (cnf.multicast, cnf.address[1])
    period = 1./cnf.rate
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, struct.pack('b', 1))
        LOGS.info("Running simulator on %s T=%s", addr, period)
        while True:
            for data in output:
                sock.sendto(data.tobytes(), addr)
                await asyncio.sleep(period)
    LOGS.info("Stopping simulator on %s T=%s", addr, period)

def _runsimulator(nbeads: int,
                  cnf: DAQClient,
                  output: Union[int, np.ndarray] = None,
                  subprocess: bool               = True) -> Optional[Process]:
    "run the simulator"
    if subprocess:
        LOGS.info("running in another process")
        return Process(target = _runsimulator, args = (nbeads, cnf, output, False))

    policy = asyncio.get_event_loop_policy()
    policy.set_event_loop(policy.new_event_loop())
    loop   = asyncio.get_event_loop()
    loop.run_until_complete(writedaq(nbeads, cnf, output))
    loop.close()
    return None

def runbeadssimulator(nbeads: int,
                      cnf: DAQClient                 = None,
                      output: Union[int, np.ndarray] = None,
                      subprocess: bool               = True) -> Optional[Process]:
    "run the simulator"
    return _runsimulator(max(0, nbeads), cnf, output, subprocess)

def runfovsimulator(cnf: DAQClient                 = None,
                    output: Union[int, np.ndarray] = None,
                    subprocess: bool               = True) -> Optional[Process]:
    "run the simulator"
    return _runsimulator(-1, cnf, output, subprocess)

class ServerSimulatorView:
    """
    view for simulating the server
    """
    def __init__(self, **_):
        self._fov:   Process = None
        self._beads: Process = None

    def observe(self, ctrl):
        "observe the controller"
        startfov   = partial(self._startfov,   ctrl)
        startbeads = partial(self._startbeads, ctrl)

        @ctrl.daq.observe
        def _onlisten(**_):
            LOGS.info("Simulators FoV(%s), Beads(%s)",
                      ctrl.daq.data.fovstarted,
                      ctrl.daq.data.beadsstarted)
            startfov()
            startbeads()

        ctrl.daq.observe("addbeads", "removebeads", startbeads)
        ctrl.theme.observe("beads", startbeads)
        ctrl.theme.observe("fov",   startfov)
        ctrl.display.observe("guiloaded", lambda: ctrl.daq.listen(True, True))

    @staticmethod
    def addtodoc(*_):
        "nothing to do"
        return

    def _startfov(self, ctrl, **_):
        proc, self._fov = self._fov, None
        if proc:
            proc.terminate()

        if ctrl.daq.data.fovstarted:
            self._fov = runfovsimulator(ctrl.daq.config.network.fov)
            LOGS.info("starting fov simulator")
            self._fov.start()

    def _startbeads(self, ctrl, **_):
        proc, self._beads = self._beads, None
        if proc:
            proc.terminate()
        nbeads = len(ctrl.daq.config.beads)
        if nbeads and ctrl.daq.data.beadsstarted:
            self._beads = runbeadssimulator(nbeads, ctrl.daq.config.network.beads)
            LOGS.info("starting beads simulator")
            self._beads.start()
