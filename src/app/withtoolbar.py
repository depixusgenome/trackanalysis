#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=unused-import
u"Updates app manager so as to deal with controllers"
from bokeh.layouts          import layout
from control.taskcontrol    import TaskController
from control.globalscontrol import GlobalsController
from view                   import BokehView
from view.undo              import UndoView
from view.globalsview       import GlobalsView
from view.toolbar           import ToolBar
from .                      import setup

def _withtoolbar(main):
    class ViewWithToolbar(BokehView):
        u"A view with the toolbar on top"
        def __init__(self, **kwa):
            self._bar      = ToolBar(**kwa)
            self._mainview = main(**kwa)
            super().__init__(**kwa)

        def close(self):
            u"remove controller"
            super().close()
            self._bar.close()
            self._mainview.close()

        def getroots(self):
            u"adds items to doc"
            children = [self._bar.getroots(), self._mainview.getroots()]
            return layout(children, sizing_mode = 'scale_width'),

    return ViewWithToolbar

setup(locals(), creator = _withtoolbar, defaultcontrols = all, defaultviews = all)
