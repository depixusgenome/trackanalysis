#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Updates app manager so as to deal with controllers"
from .launcher  import setup

VIEWS       = ('undo.UndoView', 'view.globalsview.GlobalsView',)
CONTROLS    = ('control.taskcontrol.TaskController',
               'control.globalscontrol.GlobalsController',
               'anastore.control',
               'undo.UndoController')

def _creator(main):
    from view.keypress import DpxKeyEvent
    main.KeyPressManager = DpxKeyEvent
    return main
setup(locals(), creator = _creator, defaultcontrols = CONTROLS, defaultviews = VIEWS)
