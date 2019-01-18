#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Updates app manager so as to deal with controllers"
from app.launcher  import setup
from .maincontrol  import createview

VIEWS       = ('undo.UndoView', 'taskview.tasksview.TasksView',)
CONTROLS    = ('taskcontrol.taskcontrol.TaskController',
               'taskstore.control',
               'undo.UndoController')

setup(locals(), creator = createview, defaultcontrols = CONTROLS, defaultviews = VIEWS)
