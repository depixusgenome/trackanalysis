#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"The main controller"
from   app.configuration      import ConfigurationIO
from   app.maincontrol        import BaseSuperController
from   ..control              import DAQController

class DAQSuperController(BaseSuperController):
    """
    Main controller: contains all sub-controllers.
    These share a common dictionnary of handlers
    """
    APPNAME = 'DataAcquisition'
    def __init__(self, view):
        super().__init__(view)
        self.daq = DAQController()

    def _getmaps(self):
        maps                   = super()._getmaps()
        maps['config.network'] = self.daq.config.network.config('ChainMap')
        return maps

    def _setmaps(self, maps):
        net = maps.pop('config.network', None)
        if net:
            self.daq.updatenetwork(**net)
        super()._setmaps(maps)

    def _observeargs(self):
        return (self.daq, "updatenetwork")

def createview(main, controls, views):
    "Creates a main view"
    controls = (DAQSuperController,)+tuple(controls)
    views    = (main,)+tuple(views)
    return ConfigurationIO.createview(controls, views)
