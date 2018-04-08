#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Sending orders to the server"
import socket
import struct
import asyncio

from   contextlib           import closing
from   enum                 import Enum
from   typing               import Tuple

import websockets
import numpy                as     np

from   tornado.ioloop       import IOLoop

from   ..model              import DAQBead, DAQProtocol, DAQNetwork

async def send2daq(cnf, text):
    "sends a Lua script to the DAQ"
    async with websockets.connect(cnf.websocket) as websocket:
        await websocket.send(text)

async def readdaq(cnf, output):
    """
    Reads server data and outputs it
    """
    pack     = struct.pack('4sL', socket.inet_aton(cnf.multicast), socket.INADDR_ANY)
    data     = np.zeros(cnf.packet, cnf.columns)
    address  = cnf.address
    period   = 1./cnf.rate
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

class Teensy(Enum):
    """
    all attributes that can be set in the Teensy
    """
    zmag        = "Zmag"
    zobj        = "Zobj"
    zspeed      = "Zspeed"
    xstage      = "Xstage"
    ystage      = "Ystage"
    temperature = "T0"
    led1        = "Led1"
    led2        = "Led2"

class DAQAdmin: # pylint: disable=too-many-public-methods
    """
    Allows sending orders to the DAQ server
    """
    _MSG   = "local t=hidCommand.new();t.MessageType=82;"
    _PREC  = dict(zmag = 1e-3,   x = 1e-3, y = 1e-3, tsample = 1e-2)
    def __init__(self, model: DAQNetwork) -> None:
        self.model    = model

    async def getconfig(self) -> dict:
        "get the beads tracked by the server"
        raise NotImplementedError()

    async def getcamera(self) -> dict:
        "get the beads tracked by the server"
        cnf = await self.getconfig()
        cam = cnf['daqserver']['devices']['camera']
        return {'pixels'    : (cam['aoiwidth'], cam['aoiheight']),
                'framerate' : cam['framerate']
               }

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

    async def setvalues(self, *args):
        "sets a list of values"
        msg  = self._MSG
        for i in range(0, len(args), 2):
            msg += "{}={};".format(Teensy(args[i]).value, args[i+1])
        await send2daq(self.model, msg)

class DAQAdminView:
    """
    Listen to the gui and warn the server
    """
    def __init__(self):
        self._listening = True
        self._doc       = None

    @staticmethod
    def _daq(control):
        return DAQAdmin(control.config.network)

    @classmethod
    def _set(cls, control, *args):
        async def _run():
            await cls._daq(control).setvalues(*args)
        IOLoop.current().spawn_callback(_run)

    def _onupdateprotocol(self, control = None, model = None, **_):
        if self._listening:
            if hasattr(model, "zmag"):
                async def _run():
                    daq = self._daq(control)
                    await daq.setvalues(Teensy.zmag,   model.zmag,
                                        Teensy.zspeed, model.speed)
                IOLoop.current().spawn_callback(_run)
            else:
                async def _run():
                    await self._daq(control).setprotocol(model)
                IOLoop.current().spawn_callback(_run)

    def _onbeads(self, control = None, **_):
        if not self._listening:
            async def _run():
                await self._daq(control).setbeads(control.config.beads)
            IOLoop.current().spawn_callback(_run)

    def _onstartrecording(self, control = None, **_):
        if not self._listening:
            async def _run():
                await self._daq(control).setstartrecording(control.config.record.path)
            IOLoop.current().spawn_callback(_run)

    def _onstoprecording(self, control = None, **_):
        if not self._listening:
            async def _run():
                await self._daq(control).setstoprecording()
            IOLoop.current().spawn_callback(_run)

    def _onupdatenetwork(self, control = None, **_):
        async def _run():
            daq      = self._daq(control)
            rec      = await daq.getisrecording()
            beads    = await daq.getbeads()
            protocol = await daq.getprotocol()

            def _inform():
                try:
                    if rec > 0:
                        control.startrecording(control.config.record.path, rec)
                    else:
                        control.stoprecording()
                    control.updateprotocol(protocol)
                    control.removebeads()
                    control.addbeads(beads)
                finally:
                    self._listening = False
            self._doc.add_next_tick_callback(_inform)
        IOLoop.current().spawn_callback(_run)

    def observe(self, ctrl):
        "setup observers"
        ctrl.observe(self._onupdateprotocol)
        ctrl.observe("updatebeads", "removebeads", "addbeads", self._onbeads)
        ctrl.observe(self._onstartrecording)
        ctrl.observe(self._onstoprecording)
        ctrl.observe(self._onupdatenetwork)
