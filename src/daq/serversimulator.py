#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Simulate the server"
import asyncio
import socket
import struct
from   contextlib       import closing
from   multiprocessing  import Process

import numpy        as     np

from   daq.model        import DAQClient, DAQNetwork

async def writedaq(cnf: DAQClient = None, output = None):
    """
    Reads server data and outputs it
    """
    if cnf is None:
        cnf = DAQNetwork.fov
    if output is None:
        output = 300

    if np.isscalar(output):
        tmp    = np.sin(np.arange(output, dtype = 'f4'))

        cnt    = (cnf.bytesize - cnf.offset -cnf.columns.itemsize)//4
        ncols  = len(cnf.columns.names)

        vals   = ([np.empty(output, dtype = 'f4')]*(cnf.offset//4)
                  + [np.arange(output)]
                  + [np.roll(tmp*i, i*10) for i in range(ncols-1)]
                  + [np.empty(output, dtype = 'f4')]*cnt)

        dtype  = ([(f'l{i}', 'f4') for i in range(cnf.offset//4)]
                  + cnf.columns.descr
                  +[(f'r{i}', 'f4') for i in range(cnt)])
        output = np.array([tuple(vals[j][i] for j in range(len(vals)))
                           for i in range(output)], dtype = dtype)

    sock   = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    with closing(sock):
        sock.setsockopt(socket.IPPROTO_IP,
                        socket.IP_ADD_MEMBERSHIP,
                        struct.pack('4sL',
                                    socket.inet_aton(cnf.multicast),
                                    socket.INADDR_ANY))
        sock.bind(cnf.address)
        sock.connect(cnf.address)
        while True:
            for data in output:
                sock.send(data.tobytes())

def runserversimulator(cnf: DAQClient = None, output = None, subprocess = True, **kwa):
    "run the simulator"
    if cnf is None and len(kwa) == 0:
        cnf = DAQNetwork.fov
    elif cnf is None:
        cnf = DAQClient(**kwa)

    if subprocess:
        return Process(target = runserversimulator, args = (cnf, output, False))

    loop = asyncio.get_event_loop()
    loop.run_until_complete(writedaq(cnf, output))
    loop.close()

if __name__ == '__main__':
    runserversimulator(subprocess=False)
