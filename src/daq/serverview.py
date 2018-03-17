#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"DAQ server's clients"
import socket
import struct
import asyncio

from   contextlib   import closing, suppress
from   typing       import Tuple, cast

import websockets
import numpy        as     np

from   .model       import DAQBead, DAQProtocol, DAQNetwork

async def send2daq(cnf, text):
    "sends a Lua script to the DAQ"
    async with websockets.connect(cnf.websocket) as websocket:
        await websocket.send(text)

async def readdaq(cnf, output):
    """
    Reads server data and outputs it
    """
    pack     = struct.pack('4sL',
                           socket.inet_aton(cnf.multicast),
                           socket.INADDR_ANY)
    data     = np.zeros(cnf.packet, cnf.columns)
    address  = cnf.address
    period   = cnf.period
    bytesize = cnf.bytesize
    offset   = cnf.offset
    rng      = range(len(data)-1)
    dontstop = True
    while dontstop:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(address)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, pack)
        with closing(sock):
            data[0] = sock.recvfrom(bytesize)[0][offset:]
            for i in rng:
                await asyncio.sleep(period)
                data[i] = sock.recvfrom(bytesize)[0][offset:]
            dontstop = output(data)

class DAQServerView:
    """
    Can listen to the server
    """
    _NAME = ''
    def __init__(self):
        self._task = None

    def __init_subclass__(cls, **args):
        cls._NAME = args['name']

    @classmethod
    def _sanitycheck(cls, ctrl):
        # for now the network & data configuration should remain the same
        # Otherwise the calls to the controller should be changed
        dt1 = getattr(ctrl.config.network, cls._NAME)
        dt2 = getattr(ctrl.config, cls._NAME+"data")
        assert [i for _, i in dt1.columns.descr] == [i for _, i in dt2.columns.descr]

    async def _start(self, ctrl, loop):
        self._task, task = None, cast(asyncio.Task, self._task)
        if task is not None:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task

        if getattr(ctrl.data, self._NAME+'started') and self._task is None:
            self._sanitycheck(ctrl)
            cnf  = getattr(ctrl.config.network, self._NAME)
            ctrl = getattr(ctrl, f'add{self._NAME}data')
            self._task = asyncio.ensure_future(readdaq(cnf, ctrl), loop = loop)

    def observe(self, ctrl):
        "setup observers"
        loop = asyncio.get_event_loop()
        data = self._NAME+'started'
        cnf  = self._NAME

        def _onlisten(control = None, model = None, old = None, **_):
            if model is control.data and data in old:
                self._start(control, loop)
        ctrl.observe(_onlisten)

        def _onupdatenetwork(control = None, model = None, old = None, **_):
            if model is control.config.network or cnf in old:
                self._start(control, loop)
        ctrl.observe(_onupdatenetwork)

class DAQFoVServerView(DAQServerView, name = 'fov'):
    """
    Can listen to the FoV server
    """

class DAQBeadsServerView(DAQServerView, name = 'beads'):
    """
    Can listen to the FoV server
    """

class _AwaitableDescriptor:
    __slots__ = ('_name',)
    def __init__(self):
        self._name = None

    def __set_name__(self, _, name):
        self._name = name

    def __get__(self, inst, owner):
        if inst is None:
            return self

        loop = asyncio.get_event_loop()
        return loop.run_until_complete(getattr(inst, f'get{self._name}')())

    def __set__(self, inst, val):
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(getattr(inst, f'set{self._name}')(val))

class DAQAdmin:
    """
    Allows sending orders to the DAQ server
    """
    _MSG   = "local t=hidCommand.new();t.MessageType=82;t.{}={};"
    _NAMES = dict(zmag = 'Zmag', x = 'X',  y = 'Y',  tsample = "Tsample")
    _PREC  = dict(zmag = 1e-3,   x = 1e-3, y = 1e-3, tsample = 1e-2)
    def __init__(self, model: DAQNetwork, blocking = False) -> None:
        self.model    = model
        self.blocking = blocking

    zmag        = _AwaitableDescriptor()
    temperature = _AwaitableDescriptor()
    stage       = _AwaitableDescriptor()
    beads       = _AwaitableDescriptor()
    protocol    = _AwaitableDescriptor()

    async def getbeads(self) -> Tuple[DAQBead, ...]:
        "get the beads tracked by the server"
        raise NotImplementedError()

    async def setbeads(self, beads: Tuple[DAQBead, ...]):
        "set the beads tracked by the server"
        raise NotImplementedError()

    async def getprotocol(self) -> DAQProtocol:
        "get info about the current protocol by the server"
        raise NotImplementedError()

    async def setprotocol(self, protocol: DAQProtocol):
        "set info about the current protocol by the server"
        raise NotImplementedError()

    async def wait(self, *args):
        "wait for a value to be reached"
        if len(args) == 1:
            asyncio.sleep(args[0])
        else:
            def _done(lines):
                return all(abs(lines[-1][args[i]]-args[i+1]) < self._PREC[args[i]]
                           for i in range(0, len(args), 2))
            await readdaq(self.model, _done)

    async def setzmag(self, zmag:float):
        "set the magnet position"
        await self._setvalue('zmag', zmag)

    async def setstage(self, pos:Tuple[float, float]):
        "set the stage position"
        await self._setvalue('x', pos[0], 'y', pos[1])

    async def settemperature(self, tval: float):
        "set the sample temperature"
        await self._setvalue('tsample', tval)

    async def setstartrecording(self, record: str):
        """
        tell the server to start recording
        """
        raise NotImplementedError()

    async def setstoprecording(self):
        """
        tell the server to stop recording
        """
        raise NotImplementedError()

    async def getisrecording(self) -> int:
        """
        the amount of time left in recording: -1 for no
        """
        raise NotImplementedError()

    def record(self, record: str):
        """
        record some actions into the provided file path
        """
        return self._Record(self, record)

    class _Record:
        "allows recording some experiments"
        def __init__(self, admin, record):
            self.admin  = admin
            self.record = record
        async def __aenter__(self):
            await self.admin.startrecording(self.record)
            return self.admin

        async def __aexit__(self, *_):
            await self.admin.stoprecording()

    async def _setvalue(self, *args):
        msg = "".join(self._MSG.format(self._MSG[args[i]], args[i+1])
                      for i in range(0, len(args), 2))
        await send2daq(self.model, msg)
        if self.blocking: # pylint: disable=unreachable
            await self.wait(self.model, *args)

class DAQAdminView:
    """
    Listen to the gui and warn the server
    """
    def __init__(self):
        self._listening = True

    @staticmethod
    def _daq(control):
        return DAQAdmin(control.config.network)

    @classmethod
    def _set(cls, control, name, value):
        setattr(cls._daq(control), name, value)

    def _onupdateprotocol(self, control = None, model = None, **_):
        if self._listening:
            if hasattr(model, "zmag"):
                self._set(control, "zmag", model.zmag)
            else:
                self._set(control, "protocol", model)

    def _onbeads(self, control = None, **_):
        if not self._listening:
            self._set(control, "zmag", control.config.beads)

    def _onstartrecording(self, control = None, **_):
        if not self._listening:
            cor = self._daq(control).setstartrecording(control.config.record.path)
            asyncio.get_event_loop().run_until_complete(cor)

    def _onstoprecording(self, control = None, **_):
        if not self._listening:
            cor = self._daq(control).setstoprecording()
            asyncio.get_event_loop().run_until_complete(cor)

    def _onupdatenetwork(self, control = None, **_):
        self._listening = True
        try:
            loop  = asyncio.get_event_loop().run_until_complete
            daq   = self._daq(control)
            rec   = loop(daq.getisrecording())
            if rec > 0:
                control.startrecording(control.config.record.path, rec)
            else:
                control.stoprecording()

            control.updateprotocol(daq.protocol)
            control.removebeads()
            control.addbeads(daq.beads)
        finally:
            self._listening = False

    def observe(self, ctrl):
        "setup observers"
        ctrl.observe(self._onupdateprotocol)
        ctrl.observe("updatebeads", "removebeads", "addbeads", self._onbeads)
        ctrl.observe(self._onstartrecording)
        ctrl.observe(self._onstoprecording)
        ctrl.observe(self._onupdatenetwork)
