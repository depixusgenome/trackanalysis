#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"DAQ Controller"
from   typing                   import Optional, Dict, Union, Tuple, Any, Callable
from   functools                import wraps
import numpy                    as     np
from   control.event            import Controller, NoEmission
from   control.decentralized    import updatemodel as _updatemodel
from   .model                   import DAQConfig, DAQBead
from   .data                    import DAQData

def updatemodel(self, model, kwa, force = False):
    "update the model"
    out = _updatemodel(self, model, kwa, force)
    if out is None:
        raise NoEmission()
    return out

def configemit(fcn:Callable) -> Callable:
    """
    decorator for emitting events
    """
    emitfcn = Controller.emit(fcn)

    @wraps(fcn)
    def _wrap(self, *args, **kwa):
        return None if self.config.recording.started else emitfcn(self, *args, **kwa)
    return _wrap

class DAQController(Controller):
    """
    Controller for the DAQ
    """
    def __init__(self, **kwa):
        super().__init__(**kwa)
        self.config = DAQConfig()
        self.data   = DAQData(self.config)

    @staticmethod
    def __newbead(dflt, cnf: Union[Dict[str, Any], DAQBead]) -> DAQBead:
        if isinstance(cnf, dict):
            tmp  = dict(dflt.__dict__)
            tmp.update(cnf)
        else:
            tmp  = cnf.__dict__
        return DAQBead(**tmp)

    @configemit
    def startrecording(self, path: str, duration: Optional[int]) -> dict:
        "start recording"
        args = dict(started = True, path = path, duration = duration)
        return updatemodel(self, self.config.recording, args)

    @Controller.emit
    def stoprecording(self) -> dict:
        "stop recording"
        if not self.config.recording.started:
            raise NoEmission("no recording started")
        return updatemodel(self, self.config.recording, dict(started = False))

    @configemit
    def updatenetwork(self, force = False, **kwa) -> dict:
        "update the config network"
        out               = updatemodel(self, self.config.network, kwa, force = force)
        self.config.beads = ()
        self.data.fov.clear()
        self.data.beads.clear()
        return out

    @configemit
    def updateprotocol(self, protocol) -> dict:
        "update the config protocol"
        if self.config.protocol == protocol:
            raise NoEmission
        old                  = self.config.protocol
        self.config.protocol = protocol
        return dict(control = self, model = self.config.protocol, old = old)

    @configemit
    def removebeads(self, *beads: int) -> dict:
        "remove *existing* beads"
        if len(beads) == 0:
            good = set(range(len(self.config.beads)))
        else:
            good  = set(i for i in beads if i < len(self.config.beads))
        if not good:
            raise NoEmission()

        oldconfig         = {i: self.config.beads[i] for i in beads}
        olddata           = self.data.beads
        self.config.beads = tuple(j for i, j in enumerate(self.config.beads) if i not in good)
        self.data.beads.removebeads(beads)
        return dict(control = self, beads = oldconfig, data = olddata)

    @configemit
    def updatebeads(self, *beads: Tuple[int, Union[Dict[str,Any], DAQBead]]) -> dict:
        "update *existing* beads"
        # find out if there's anything to updatemodel
        old   = self.config.beads
        new   = {i: self.__newbead(old[i], j) for i, j in dict(beads).items()}
        new   = {i: j for i, j in new.items() if j.__dict__ != old[i].__dict__}
        if len(new) == 0:
            raise NoEmission()

        self.config.beads = tuple(new.get(i, j) for i, j in enumerate(self.config.beads))
        return dict(control = self, beads = new)

    def addbeads(self, *beads: Union[Dict[str, Any], DAQBead]):
        "add *new* beads"
        if len(beads) == 0:
            return

        self.config.beads     += tuple(self.__newbead(self.config.defaultbead, i) for i in beads)
        self.data.beads.nbeads = len(self.config.beads)
        self.handle("addbeads",
                    self.emitpolicy.outasdict,
                    dict(control = self, added = len(beads)))
        self.setcurrentbead(len(self.config.beads)-1)

    @Controller.emit
    def listen(self, fov, beads) -> dict:
        "add lines of data"
        if fov:
            self.data.fov   = self.data.fov  .create(self.config, self.data.fov.maxlength)
        if beads:
            self.data.beads = self.data.beads.create(self.config, self.data.beads.maxlength)
        return updatemodel(self, self.data, dict(fovstarted = fov, beadsstarted = beads))

    def addfovdata(self, lines: np.ndarray) -> dict:
        "add lines of data"
        return self.handle("addfovdata",
                           self.emitpolicy.outasdict,
                           dict(control = self, lines = lines))

    def addbeadsdata(self, lines: Dict[int, np.ndarray]) -> dict:
        "add lines of data"
        return self.handle("addbeadsdata",
                           self.emitpolicy.outasdict,
                           dict(control = self, lines = lines))

    def setcurrentbead(self, bead: Optional[int]) -> dict:
        "changes the current bead"
        return self.handle("currentbead", self.emitpolicy.outasdict,
                           dict(control = self, bead = bead))

    def setup(self, ctrl):
        """
        setup the daq data
        """
        def _do(name, old):
            mlen = getattr(ctrl.theme.model(name+'memory'),   'maxlength', 10000)
            vect = getattr(self.data, name)
            if mlen != vect.maxlength:
                old[name] = getattr(self.data, name+'started')
                setattr(self.data, 'fov', type(vect)(ctrl, mlen))

        def _onupdate(**_):
            old: Dict[str, bool] = {}
            _do('fov',   old)
            _do('beads', old)
            if old:
                self.handle("listen", self.emitpolicy.outasdict,
                            dict(control = self, old = old))

        for i in ("fov", "beads"):
            if i in ctrl.theme:
                ctrl.theme.observe(i, _onupdate)
                ctrl.theme.observe("started"+i, _onupdate)
        _onupdate()
