#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"DAQ Controller"
from   typing                   import Optional, Dict, Union, Tuple, Any, Callable
from   functools                import wraps
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
    def updatedefaultbead(self, **kwa) -> dict:
        "update the config network"
        return updatemodel(self, self.config.defaultbead, kwa)

    @configemit
    def updatedatamaxlength(self, fov = None, beads = None) -> dict:
        "update the config network"
        old: Dict[str, int] = dict()
        if fov is not None and fov != self.data.fov.maxlength:
            assert not self.data.fovstarted
            old['fov']    = self.data.fov.maxlength
            self.data.fov = self.data.fov.create(self.config, fov)

        if beads is not None and beads != self.data.beads.maxlength:
            assert not self.data.beadsstarted
            old['beads']    = self.data.beads.maxlength
            self.data.beads = self.data.beads.create(self.config, beads)

        if not old:
            raise NoEmission()
        return old

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
    def listen(self, fov = None, beads = None) -> dict:
        "add lines of data"
        if fov is None:
            fov             = self.data.fovstarted
        elif fov and not self.data.fovstarted:
            self.data.fov   = self.data.fov  .create(self.config, self.data.fov.maxlength)

        if beads is None:
            beads           = self.data.fovstarted
        elif beads and not self.data.beadsstarted:
            self.data.beads = self.data.beads.create(self.config, self.data.beads.maxlength)

        return updatemodel(self, self.data, dict(fovstarted = fov, beadsstarted = beads))

    def setcurrentbead(self, bead: Optional[int]) -> dict:
        "changes the current bead"
        return self.handle("currentbead", self.emitpolicy.outasdict,
                           dict(control = self, bead = bead))
