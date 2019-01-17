#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"The main task controller"
from   app.maincontrol         import BaseSuperController, createview as _createview
from   taskcontrol.taskcontrol import TaskController

class SuperController(BaseSuperController):
    """
    Main controller: contains all sub-controllers.
    These share a common dictionnary of handlers
    """
    def __init__(self, view):
        hdl: dict    = dict()
        self.tasks   = TaskController(handlers = hdl)
        super().__init__(view, handlers = hdl)

    def _observe(self, keys):
        "starts the controler"
        super()._observe(keys)
        self.tasks.setup(self)

    def _observeargs(self):
        return (self.tasks, "opentrack",
                self.tasks, "addtask",
                self.tasks, "updatetask",
                self.tasks, "removetask",
                self.tasks, "closetrack")

def createview(main, controls, views):
    "Creates a main view"
    return _createview(SuperController, main, controls, views)
