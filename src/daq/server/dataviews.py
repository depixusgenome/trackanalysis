#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"DAQ server's clients"
import socket
import struct
import asyncio
import time

from   functools          import partial
from   typing             import TypeVar, Generic, List, Tuple, Any

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
    name        = "memory"
    maxlength   = 10000
    packet      = 3
    period      = 1/15. # seconds
    timeout     = .05
    maxerrcount = 5
    maxerrtime  = 5.
    errsleep    = .3
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
        name = self._NAME+name
        if name in old and getattr(ctrl.daq.data, name):
            async def _start():
                await self.__start(ctrl)
            IOLoop.current().spawn_callback(_start)

    async def __readdaq(self, index, cnf, data, call): # pylint: disable=too-many-locals
        """
        Reads server data and outputs it
        """
        pack     = struct.pack('4sL',
                               socket.inet_aton(cnf.multicast),
                               socket.INADDR_ANY)
        address  = cnf.address
        timeout  = self._theme.timeout
        period   = self._theme.period
        bytesize = data.view().dtype.itemsize
        rng      = tuple(slice(i,i+1) for i in range(self._theme.packet))
        errs: List[Tuple[float, Any]] = []
        def _err(errs, *args):
            errs.append((time.time(),)+args)
            if len(errs) >= self._theme.maxerrcount:
                return [i for i in errs if errs[-1][0]-i[0] < self._theme.maxerrtime]
            return errs

        while self._index == index and len(errs) < self._theme.maxerrcount:
            cur, ind = data.getnextlines(rng[-1].stop)
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                    sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, pack)
                    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    sock.settimeout(timeout)
                    sock.bind(address)
                    for i in rng:
                        sock.recv_into(cur[i], bytesize)
                    data.applynextlines(ind)
                    call(cur)
            except InterruptedError as exc:
                errs = _err(errs, exc)
                await asyncio.sleep(self._theme.errsleep)
            except socket.timeout as exc:
                errs = _err(errs, exc)
                await asyncio.sleep(self._theme.errsleep)
            except socket.error as exc:
                errs = _err(errs, exc)
                await asyncio.sleep(self._theme.errsleep)
            else:
                await asyncio.sleep(period)
        return errs[-1][1] if self._theme.maxerrcount <= len(errs) else None

    async def __start(self, ctrl):
        ctrl        = getattr(ctrl, 'daq', ctrl)
        self._index = index = self._index+1
        cnf         = getattr(ctrl.config.network, self._NAME)
        call        = getattr(ctrl, f'add{self._NAME}data')
        data        = getattr(ctrl.data, self._NAME)
        if not (getattr(ctrl.data, self._NAME+'started') or self._index != index):
            LOGS.info("Forced stop on %s[%d]@%s", self._NAME, index-1, cnf.address)
            return

        LOGS.info("starting %s[%d]@%s", self._NAME, index, cnf.address)
        err = await self.__readdaq(index, cnf, data, call)
        if err:
            LOGS.info("Too many errors on %s[%d]@%s: last is '%s'",
                      self._NAME, index, cnf.address, err)
            async def _err():
                ctrl.listen(**{self._NAME:False})
            await _err()
        else:
            LOGS.info("Stopped %s[%d]@%s", self._NAME, index, cnf.address)

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
