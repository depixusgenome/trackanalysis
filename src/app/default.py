#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Updates app manager so as to deal with controllers"
from .launcher  import setup

VIEWS       = ('undo.UndoView', 'view.tasksview.TasksView',)
CONTROLS    = ('control.taskcontrol.TaskController',
               'control.globalscontrol.GlobalsController',
               'anastore.control',
               'undo.UndoController')

setup(locals(), defaultcontrols = CONTROLS, defaultviews = VIEWS)
