#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"DAQ server's clients"
import socket
import struct
import asyncio

from   contextlib         import closing
from   functools          import partial
from   typing             import TypeVar, Generic

from   tornado.ioloop     import IOLoop

from   utils              import initdefaults
from   utils.logconfig    import getLogger
from   utils.inspection   import templateattribute
from   ..data             import RoundRobinVector, FoVRoundRobinVector, BeadsRoundRobinVector

LOGS = getLogger(__name__)

class DAQMemory:
    """
    Relative to the amount of raw memory to keep
    """
    name      = "memory"
    maxlength = 10000
    packet    = 1
    timeout   = .05
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

    def _onstart(self, ctrl, name, old = None, **_):
        if self._NAME+name in old:
            async def _start():
                await self.__start(ctrl)
            IOLoop.current().spawn_callback(_start)

    async def __readdaq(self, index, cnf, data, call): # pylint: disable=too-many-locals
        """
        Reads server data and outputs it
        """
        LOGS.info("started %s client", self._NAME)
        pack     = struct.pack('4sL',
                               socket.inet_aton(cnf.multicast),
                               socket.INADDR_ANY)
        address  = cnf.address
        period   = 1./cnf.rate
        bytesize = data.view().dtype.itemsize
        rng      = range(1, self._theme.packet)
        while self._index == index:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.bind(address)
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, pack)
            sock.setblocking(False)
            cur, ind = data.getnextlines(rng.stop)
            with closing(sock):
                try:
                    sock.recv_into(cur[:1], bytesize)
                    for i in rng:
                        await asyncio.sleep(period)
                        sock.recv_into(cur[i:i+1], bytesize)
                    data.applynextlines(ind)
                    call(cur)
                except socket.error:
                    pass
                finally:
                    await asyncio.sleep(period)

    async def __start(self, ctrl):
        ctrl        = getattr(ctrl, 'daq', ctrl)
        self._index = index = self._index+1
        cnf         = getattr(ctrl.config.network, self._NAME)
        call        = getattr(ctrl, f'add{self._NAME}data')
        data        = getattr(ctrl.data, self._NAME)
        if not (getattr(ctrl.data, self._NAME+'started') or self._index != index):
            LOGS.info("stopping %s client", self._NAME)
            return

        LOGS.info("starting %s client", self._NAME)
        await self.__readdaq(index, cnf, data, call)

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
