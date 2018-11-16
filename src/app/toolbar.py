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

class _AppName:
    def __get__(self, _, owner):
        name = templateattribute(owner, 1).__name__
        return name.lower().replace('view', '')

class ViewWithToolbar(Generic[TOOLBAR, VIEW]):
    "A view with the toolbar on top"
    APPNAME = _AppName()
    def __init__(self, ctrl = None, **kwa):
        assert not isinstance(templateattribute(self, 0), TypeVar)
        self._bar      = templateattribute(self, 0)(ctrl = ctrl, **kwa)
        self._mainview = templateattribute(self, 1)(ctrl = ctrl, **kwa)

    def ismain(self, ctrl):
        "sets-up the main view as main"
        getattr(self._mainview, 'ismain', lambda _: None)(ctrl)

    def close(self):
        "remove controller"
        self._bar.close()
        self._mainview.close()

    def observe(self, ctrl):
        "observe the controller"
        self._bar.observe(ctrl)
        self._mainview.observe(ctrl)

    def addtodoc(self, ctrl, doc):
        "adds items to doc"
        tbar   = self._bar.addtodoc(ctrl, doc)
        others = self._mainview.addtodoc(ctrl, doc)
        mode   = ctrl.theme.get('main', 'sizingmode')
        while isinstance(others, (tuple, list)) and len(others) == 1:
            others = others[0]

        if isinstance(others, list):
            children = [tbar] + others
        elif isinstance(others, tuple):
            children = [tbar, layout(others, sizing_mode = mode)]
        else:
            children = [tbar, others]

        return column(children, sizing_mode = mode, css_classes = ["dpx-tb-layout"])

def toolbarview(tbar, main) -> type:
    "return the view with toolbar"
    class ToolbarView(ViewWithToolbar[getclass(tbar), getclass(main)]): # type: ignore
        "Toolbar view"
        pass
    return ToolbarView

def createview(main, controls, views):
    "Creates an app with a toolbar"
    return _createview(toolbarview('view.toolbar.BeadToolbar', main), controls, views)

setup(locals(), creator = createview, defaultcontrols = CONTROLS, defaultviews = VIEWS)
