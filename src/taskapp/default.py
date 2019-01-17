#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Updates app manager so as to deal with controllers"
from app.launcher  import setup

VIEWS       = ('undo.UndoView', 'taskview.tasksview.TasksView',)
CONTROLS    = ('taskcontrol.taskcontrol.TaskController',
               'taskstore.control',
               'undo.UndoController')

setup(locals(), defaultcontrols = CONTROLS, defaultviews = VIEWS)
