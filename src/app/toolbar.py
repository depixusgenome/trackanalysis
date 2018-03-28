#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Updates app manager so as to deal with controllers and toolbar"
from typing           import Generic, TypeVar

from bokeh.layouts    import layout, column

from utils.inspection import getclass, templateattribute
from .launcher        import setup
from .maincontrol     import createview as _createview
from .default         import VIEWS, CONTROLS


TOOLBAR = TypeVar("TOOLBAR")
VIEW    = TypeVar("VIEW")

class ViewWithToolbar(Generic[TOOLBAR, VIEW]):
    "A view with the toolbar on top"
    def __init_subclass__(cls, **_):
        name        = templateattribute(cls, 1).__name__
        cls.APPNAME = name.lower().replace('view', '')

    def __init__(self, ctrl = None, **kwa):
        self._bar      = templateattribute(self, 0)(ctrl = ctrl, **kwa)
        self._mainview = templateattribute(self, 1)(ctrl = ctrl, **kwa)

    def ismain(self, ctrl):
        "sets-up the main view as main"
        getattr(self._mainview, 'ismain', lambda _: None)(ctrl)

    def close(self):
        "remove controller"
        self._bar.close()
        self._mainview.close()

    def addtodoc(self, ctrl, doc):
        "adds items to doc"
        tbar   = self._bar.addtodoc(ctrl, doc)
        others = self._mainview.addtodoc(ctrl, doc)
        mode   = ctrl.theme.get('main', 'sizingmode', 'fixed')
        while isinstance(others, (tuple, list)) and len(others) == 1:
            others = others[0]

        if isinstance(others, list):
            children = [tbar] + others
        elif isinstance(others, tuple):
            children = [tbar, layout(others, **mode)]
        else:
            children = [tbar, others]

        return column(children, **mode)

def createview(main, controls, views, tbar = None):
    "Creates an app with a toolbar"
    if tbar is None:
        from view.toolbar     import BeadToolbar
        tbar = BeadToolbar
    else:
        tbar = getclass(tbar)

    cls = ViewWithToolbar[tbar, getclass(main)] # type: ignore
    return _createview(cls, controls, views)

setup(locals(), creator = createview, defaultcontrols = CONTROLS, defaultviews = VIEWS)
