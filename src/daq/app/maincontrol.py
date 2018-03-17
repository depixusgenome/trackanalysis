#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"The main controller"
from   control.event           import EmitPolicy
from   app.configuration       import ConfigurationIO
from   ..control               import DAQController, DecentralizedController

class DAQSuperController:
    """
    Main controller: contains all sub-controllers.
    These share a common dictionnary of handlers
    """
    APPNAME    = 'DataAcquisition'
    APPSIZE    = [1200, 1000]
    CATCHERROR = True
    FLEXXAPP   = None
    def __init__(self, view):
        self.topview = view
        self.daq     = DAQController()
        self.theme   = DecentralizedController() # everything static settings
        self.display = DecentralizedController() # everything dynamic settings

    emitpolicy = EmitPolicy

    @property
    def _maps(self):
        maps = {'config': {i: dict(j.__dict__)      for i, j in self.daq.config.__dict__.items()},
                'theme':  dict(**{i: dict(j.__dict__) for i, j in self.theme.objects.items()},
                               appsize = self.APPSIZE, appname = self.APPNAME)}
        maps['config']['catcherror'] = self.CATCHERROR

    @_maps.setter
    def _maps(self, maps):
        for i, j in maps['config']:
            getattr(self.daq.config, i).__dict__.update(j)
        for i, j in maps['theme']:
            self.theme.objects[i].__dict__.update(j)

    def startup(self):
        "starts the control.pyler"
        self._maps = ConfigurationIO(self).startup(self._maps)

    def close(self):
        "remove controller"
        top, self.topview = self.topview, None
        if top is None:
            return

        ConfigurationIO(self).writeuserconfig(self._maps)
        top.close()
        if self.FLEXXAPP:
            self.FLEXXAPP.close()

def createview(main, controls, views):
    "Creates a main view"
    views    = (main,)+views
    controls = (DAQSuperController,)+controls
    cls      = ConfigurationIO.createview(controls, views, 'theme')
    def __init__(self):
        "sets up the controller, then initializes the view"
        ctrl = self.MainControl(self)
        keys = self.KeyPressManager(ctrl = ctrl) if self.KeyPressManager else None
        main.__init__(self, ctrl = ctrl, keys = keys)
        main.ismain(self)

        ctrl.startup()
        for i in cls.__bases__:
            i.observe(self, ctrl) # type: ignore
    cls.__init__ = __init__       # type: ignore
    return cls
