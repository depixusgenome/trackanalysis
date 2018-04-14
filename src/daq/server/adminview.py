#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Sending orders to the server"
import socket
import struct
import asyncio

from   contextlib           import closing
from   enum                 import Enum
from   typing               import Tuple, Optional, cast

import websockets
import numpy                as     np

from   tornado.ioloop       import IOLoop

from   ..model              import DAQBead, DAQProtocol, DAQNetwork, DAQManual

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
    zmag        = "zmag"
    zobj        = "zobj"
    vmag        = "vmag"
    x           = "x"   # pylint: disable=invalid-name
    y           = "y"   # pylint: disable=invalid-name
    startTime   = "startTime"
    tbox        = "tbox"
    intLed1     = "intLed1"
    intLed2     = "intLed2"

class DAQAdmin: # pylint: disable=too-many-public-methods
    """
    Allows sending orders to the DAQ server
    """
    _CMD    = "local {} = hidCommand.new();"
    _SCRIPT = "local {} = hidCommandScript.new();"
    _BEGIN  = "{}.beginPhase({});"
    _ADD    = "{}.addPhase({});"
    _SEND   = "daq_sendCommand({});"
    _PREC   = dict(zmag = 1e-3,   x = 1e-3, y = 1e-3, tsample = 1e-2)
    def __init__(self, model: DAQNetwork) -> None:
        self.model    = model

    def run(self, fcn, *args):
        "runs a coroutine"
        if fcn is not None:
            if isinstance(fcn, str):
                fcn = getattr(self, fcn)
            IOLoop.current().spawn_callback(fcn, *args)

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

    def setprotocol(self, protocol: DAQProtocol) -> Coroutine:
        "set info about the current protocol by the server"
        return send2daq(self.model, self._setprotocol(protocol))

    async def wait(self, *args):
        "wait for a value to be reached"
        if len(args) == 1:
            await asyncio.sleep(args[0])
        else:
            def _done(lines):
                return all(abs(lines[-1][args[i]]-args[i+1]) < self._PREC[args[i]]
                           for i in range(0, len(args), 2))
            await readdaq(self.model, _done)

    async def setstartrecording(self, record: str):
        """
        tell the server to start recording
        """
        if not record:
            return
        raise NotImplementedError()

    async def setstoprecording(self):
        """
        tell the server to stop recording
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

    def setvalues(self, *args) -> Coroutine:
        "sets a list of values"
        msg = self._setvalues("t", *args)+self._SEND.format("t")
        return send2daq(self.model, msg)

    def _setprotocol(self, protocol: DAQProtocol) -> str:
        if isinstance(protocol, DAQManual):
            msg = self._setvalues("s",
                                  Teensy.zmag, protocol.zmag,
                                  Teensy.vmag, protocol.speed)
        else:
            phase = [i for i in protocol.phases if i.zmag is not None][-1]
            msg   = (self._setvalues("f", Teensy.zmag, phase.zmag, Teensy.vmag, phase.speed)
                     +self._SCRIPT.format("s"))
            for i, phase in enumerate(protocol.phases):
                msg += (self._setvalues(f"p{i}",
                                        Teensy.zmag,      phase.zmag,
                                        Teensy.vmag,      phase.speed,
                                        Teensy.startTime, protocol.phases[i-1].duration)
                        +(self._BEGIN if i == 0 else self._ADD).format("s", f"p{i}"))

        return msg + self._SEND.format("s")

    def _setvalues(self, name, *args) -> str:
        "sets a list of values"
        msg  = self._CMD.format(name)
        for i in range(0, len(args), 2):
            if args[i+1] is not None:
                msg += "{}.{}={};".format(name, Teensy(args[i]).value, args[i+1])
        return msg

class DAQAdminView:
    """
    Listen to the gui and warn the server
    """
    def __init__(self, **_):
        self._listening = True
        self._doc       = None

    def observe(self, ctrl):
        "observe the controller"

        def observe(fcn):
            "create an observe method"
            @ctrl.daq.observe(fcn.__name__[3:])
            def _wrapped(self, control = None, **kwa):
                if not self._listening:
                    daq  = DAQAdmin(control.config.network)
                    daq.run(*fcn(daq, control = control, **kwa))

        @observe
        def _onupdateprotocol(_1, model = None, **_2):
            return (('setprotocol', model) if not model.ismanual() else
                    ('setvalues', Teensy.zmag, model.zmag, Teensy.vmag, model.speed))

        @observe
        def _onupdatebeads(_1, control = None, **_2):
            return ('setbeads', control.config.beads)

        @observe
        def _onaddbeads(_1, control = None, **_2):
            return ('setbeads', control.config.beads)

        @observe
        def _onremovebeads(_1, control = None, **_2):
            return ('setbeads', control.config.beads)

        @observe
        def _onstartrecording(_1, control = None, **_2):
            return ('setstartrecording', control.config.record.path)

        @observe
        def _onstoprecording(_1, **_2):
            return ('setstoprecording',)

        @observe
        def _onupdatenetwork(daq, control = None, **_):
            async def _run():
                beads = await daq.getbeads()
                def _inform():
                    self._listening = True
                    try:
                        control.removebeads()
                        control.addbeads(beads)
                    finally:
                        self._listening = False
                self._doc.add_next_tick_callback(_inform)
            return (_run,)
