#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Simulate the server"
import asyncio
import socket
import struct
from   contextlib       import closing
from   functools        import partial
from   multiprocessing  import Process
from   typing           import Union, Optional

import numpy        as     np

from   daq.model        import DAQClient, DAQNetwork

async def writedaq(nbeads: int, cnf: DAQClient = None, output = None):
    """
    Reads server data and outputs it
    """
    if cnf is None:
        cnf = DAQNetwork.fov if nbeads < 0 else DAQNetwork.beads

    if output is None:
        output = 300

    if np.isscalar(output):
        tmp    = np.sin(np.arange(output, dtype = 'f4')/output*6*np.pi)
        dtype  = cnf.fovtype() if nbeads < 0 else cnf.beadstype(nbeads)
        vals   = [np.empty(output, dtype = 'f4')  if j == '_' else
                  np.arange(output, dtype = 'i8') if k.endswith('i8') else
                  np.roll(tmp*(i+1), i*10) for i, (j, k) in enumerate(dtype.desc)]
        output = np.array([tuple(vals[j][i] for j in range(len(vals)))
                           for i in range(output)], dtype = dtype)

    addr   = cnf.multicast, cnf.address[1]
    period = 1./cnf.rate
    sock   = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    with closing(sock):
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, struct.pack('b', 1))
        sock.connect(addr)
        while True:
            for data in output:
                sock.send(data.tobytes())
                await asyncio.sleep(period)

def runsimulator(nbeads: int,
                 cnf: DAQClient                 = None,
                 output: Union[int, np.ndarray] = None,
                 subprocess: bool               = True,
                 **kwa) -> Optional[Process]:
    "run the simulator"
    if cnf is None and len(kwa) == 0:
        cnf = DAQNetwork.fov if nbeads < 0 else DAQNetwork.beads
    elif cnf is None:
        cnf = DAQClient(**kwa)

    if subprocess:
        return Process(target = runsimulator, args = (nbeads, cnf, output, False))

    loop = asyncio.get_event_loop()
    loop.run_until_complete(writedaq(nbeads, cnf, output))
    loop.close()
    return None

def runbeadssimulator(nbeads: int,
                      cnf: DAQClient                 = None,
                      output: Union[int, np.ndarray] = None,
                      subprocess: bool               = True,
                      **kwa) -> Optional[Process]:
    "run the simulator"
    return runsimulator(max(0, nbeads), cnf, output, subprocess, **kwa)

def runfovsimulator(cnf: DAQClient                 = None,
                    output: Union[int, np.ndarray] = None,
                    subprocess: bool               = True,
                    **kwa) -> Optional[Process]:
    "run the simulator"
    return runsimulator(-1, cnf, output, subprocess, **kwa)

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
        def _onlisten(fovstarted   = False, # pylint: disable=unused-variable
                      beadsstarted = False,
                      **_):
            if fovstarted:
                startfov()
            if beadsstarted:
                startbeads()

        ctrl.daq.observe("addbeads", "removebeads", startbeads)
        ctrl.theme.observe("beads", startbeads)
        ctrl.theme.observe("fov",   startfov)
        ctrl.display.observe("applicationstarted", lambda: ctrl.daq.listen(True, True))

    @staticmethod
    def addtodoc(*_):
        "nothing to do"
        return

    def _startfov(self, ctrl):
        proc, self._fov = self._fov, None
        if proc:
            proc.terminate()

        self._fov = runfovsimulator(ctrl.daq.config.network.fov)
        self._fov.start()

    def _startbeads(self, ctrl):
        proc, self._beads = self._beads, None
        if proc:
            proc.terminate()
        nbeads = len(ctrl.daq.config.beads)
        if nbeads:
            self._beads = runbeadssimulator(nbeads, ctrl.daq.config.network.beads)
            self._beads.start()

if __name__ == '__main__':
    runsimulator(-1, subprocess=False)
