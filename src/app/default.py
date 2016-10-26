#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=unused-import
u"Updates app manager so as to deal with controllers"
from control.taskcontrol    import TaskController
from control.globalscontrol import GlobalsController
from view.undo              import UndoView
from view.globalsview       import GlobalsView
from .                      import setup

setup(locals(), defaultcontrols = all, defaultviews = all)
