#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=unused-import
u"Updates app manager so as to deal with controllers"
from control.taskcontrol    import TaskController
from control.globalscontrol import GlobalsController
from view                   import FlexxView, ui
from view.undo              import UndoView
from view.globalsview       import GlobalsView
from view.toolbar           import ToolBar
from .                      import setup

def _withtoolbar(main):
    class ViewWithToolbar(FlexxView):
        u"A view with the toolbar on top"
        def init(self):
            with ui.VBox(flex = 0):
                ToolBar(flex = 0)
                main   (flex = 1)
    return ViewWithToolbar

setup(locals(), creator = _withtoolbar, defaultcontrols = all, defaultviews = all)
