#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"DAQ server's clients"
import socket
import struct
import time

from   concurrent.futures       import ThreadPoolExecutor
from   functools                import partial
from   typing                   import TypeVar, Generic, List, Tuple, Any

from   tornado.ioloop           import IOLoop
from   tornado.platform.asyncio import to_tornado_future

from   utils                    import initdefaults
from   utils.logconfig          import getLogger
from   utils.inspection         import templateattribute
from   ..data                   import RoundRobinVector, FoVRoundRobinVector, BeadsRoundRobinVector

LOGS = getLogger(__name__)

class DAQMemory:
    """
    Relative to the amount of raw memory to keep
    """
    name        = "memory"
    maxlength   = 10000
    packet      = 15
    contigs     = 15
    timeout     = .05
    maxerrcount = 5
    maxerrtime  = 60.
    errsleep    = 5.
    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        pass

DATA = TypeVar('DATA', bound = RoundRobinVector)

class DAQServerView(Generic[DATA]):
    """
    Can listen to the server
    """
    _NAME = ''
    _data: DATA
    def __init__(self, **kwa) -> None:
        self._index = 0
        self._theme = DAQMemory(name = self._NAME+'memory', **kwa)

    def observe(self, ctrl):
        "setup observers"
        if self._theme in ctrl.theme:
            return

        ctrl.theme.add(self._theme)
        ctrl.daq.observe(listen        = partial(self._onstart, ctrl, 'started'),
                         updatenetwork = partial(self._onstart, ctrl, ''))

    def close(self):
        "stop reading the daq"
        self._index += 1

    def _onstart(self, ctrl, name, old = None, **_):
        name = self._NAME+name
        if name in old and getattr(ctrl.daq.data, name):
            async def _start():
                await self.__start(ctrl)
            IOLoop.current().spawn_callback(_start)

    def __readdaq(self, index, ctrl):
        """
        Reads server data and outputs it
        """
        theme                         = self._theme
        errs: List[Tuple[float, Any]] = []
        while self._index == index and len(errs) < theme.maxerrcount:
            try:
                cnf         = getattr(ctrl.config.network, self._NAME)
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP,
                                struct.pack('4sL',
                                            socket.inet_aton(cnf.multicast),
                                            socket.INADDR_ANY))
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                sock.settimeout(theme.timeout)
                sock.bind      (cnf.address)

                for _ in range(theme.contigs):
                    data     = getattr(ctrl.data, self._NAME)
                    cur, ind = data.getnextlines(theme.packet)
                    bytesize = cur.dtype.itemsize
                    for i in range(theme.packet):
                        sock.recv_into(cur[i:i+1], bytesize)
                    data.applynextlines(ind)

            except OSError as exc:
                errs.append((time.time(),exc))
                if len(errs) >= theme.maxerrcount:
                    errs = [i for i in errs if errs[-1][0]-i[0] < theme.maxerrtime]
                time.sleep(theme.errsleep)

            finally:
                sock.close()

        return errs[-1][1] if theme.maxerrcount <= len(errs) else None

    async def __start(self, ctrl):
        ctrl        = getattr(ctrl, 'daq', ctrl)
        self._index = index = self._index+1
        addr        = getattr(ctrl.config.network, self._NAME).address
        if not (getattr(ctrl.data, self._NAME+'started') or self._index != index):
            LOGS.info("Forced stop on %s[%d]@%s", self._NAME, index-1, addr)
            return

        LOGS.info("starting %s[%d]@%s", self._NAME, index, addr)
        with ThreadPoolExecutor(1) as pool:
            err = await to_tornado_future(pool.submit(self.__readdaq, index, ctrl))

        if err:
            LOGS.info("Too many errors on %s[%d]@%s: last is '%s'",
                      self._NAME, index, addr, err)
            async def _err():
                ctrl.listen(**{self._NAME:False})
            await _err()
        else:
            LOGS.info("Stopped %s[%d]@%s", self._NAME, index, addr)

    def _createdata(self, ctrl):
        templateattribute(self, 0).create(ctrl, self._theme.maxlength) # type: ignore

class DAQFoVServerView(DAQServerView[FoVRoundRobinVector]):
    """
    Can listen to the FoV server
    """
    _NAME = 'fov'

class DAQBeadsServerView(DAQServerView[BeadsRoundRobinVector]):
    """
    Can listen to the FoV server
    """
    _NAME = 'beads'
