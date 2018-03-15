#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"DAQ server's clients"
import socket
import struct
import asyncio
import time
from   contextlib   import contextmanager, closing, suppress
from   typing       import Tuple, cast
import numpy        as     np
from   .model       import DAQBead, DAQProtocol, DAQNetwork

async def readserver(cnf, output):
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
    def __init__(self, ctrl):
        self._task = None
        self._ctrl = ctrl

    def __init_subclass__(cls, **args):
        cls._NAME = args['name']

    def _sanitycheck(self):
        # for now the network & data configuration should remain the same
        # Otherwise the calls to the controller should be changed
        dt1   = getattr(self._ctrl.config.network, self._NAME)
        dt2   = getattr(self._ctrl.config, self._NAME+"data")
        assert [i for _, i in dt1.columns.descr] == [i for _, i in dt2.columns.descr]

    async def _start(self, loop):
        self._task, task = None, cast(asyncio.Task, self._task)
        if task is not None:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task

        if getattr(self._ctrl.data, self._NAME+'started') and self._task is None:
            self._sanitycheck()
            cnf  = getattr(self._ctrl.config.network, self._NAME)
            ctrl = getattr(self._ctrl, f'add{self._NAME}data')
            self._task = asyncio.ensure_future(readserver(cnf, ctrl), loop = loop)

    def observe(self):
        "setup observers"
        loop = asyncio.get_event_loop()
        data = self._NAME+'started'
        cnf  = self._NAME

        def _onlisten(model = None, old = None):
            if model is self._ctrl.data and data in old:
                self._start(loop)
        self._ctrl.observe(_onlisten)

        def _onupdatenetwork(model = None, **_):
            if model is self._ctrl.config.network or cnf in old:
                self._start(loop)
        self._ctrl.observe(_onupdatenetwork)

class DAQFoVServerView(DAQServerView, name = 'fov'):
    """
    Can listen to the FoV server
    """

class DAQBeadsServerView(DAQServerView, name = 'beads'):
    """
    Can listen to the FoV server
    """

class DAQAdmin:
    """
    Allows sending orders to the DAQ server
    """
    def __init__(self, model: DAQNetwork, blocking = False) -> None:
        self.model    = model
        self.blocking = blocking

    @property
    def beads(self) -> Tuple[DAQBead, ...]:
        "get the beads tracked by the server"
        raise NotImplementedError()

    @beads.setter
    def beads(self, beads: Tuple[DAQBead, ...]):
        "set the beads tracked by the server"
        raise NotImplementedError()

    @property
    def protocol(self) -> DAQProtocol:
        "get info about the current protocol by the server"
        raise NotImplementedError()

    @protocol.setter
    def protocol(self, protocol: DAQProtocol):
        "set info about the current protocol by the server"
        raise NotImplementedError()

    def wait(self, name, value = None, delta = 1e-3):
        "wait for a value to be reached"
        if value is None:
            time.sleep(name)
        elif name == ('time', 'seconds'):
            time.sleep(value)
        else:
            readserver(self.model, lambda i: abs(i[-1][name] - value) < delta)

    zmag        = property() # property is write-only
    temperature = property() # property is write-only
    stage       = property() # property is write-only

    @zmag.setter
    def zmag(self, zmag:float):
        "set the magnet position"
        self._setalue('zmag', zmag)

    @stage.setter
    def stage(self, pos:Tuple[float, float]):
        "set the stage position"
        self._setalue('x', pos[0])
        self._setalue('y', pos[1])

    @temperature.setter
    def temperature(self, tval: float):
        "set the sample temperature"
        self._setalue('tsample', tval)

    def startrecording(self, record: str):
        """
        tell the server to start recording
        """
        raise NotImplementedError()

    def stoprecording(self):
        """
        tell the server to stop recording
        """
        raise NotImplementedError()

    def isrecording(self) -> int:
        """
        the amount of time left in recording: -1 for no
        """
        raise NotImplementedError()

    @contextmanager
    def record(self, record: str):
        """
        record some actions into the provided file path
        """
        self.startrecording(record)
        yield self
        self.stoprecording()

    def _setalue(self, name, value, delta = None):
        raise NotImplementedError()
        if self.blocking and delta: # pylint: disable=unreachable
            self.wait(self.model, name, value)

class DAQAdminView:
    """
    Listen to the gui and warn the server
    """
    def __init__(self):
        self._listening = True

    @staticmethod
    def _daq(control):
        DAQAdmin(control.config.network)

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
            self._daq(control).startrecording(control.config.record.path)

    def _onstoprecording(self, control = None, **_):
        if not self._listening:
            self._daq(control).stoprecording()

    def _onupdatenetwork(self, control = None, **_):
        self._listening = True
        try:
            daq = self._daq(control)
            rec = daq.isrecording()
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
