#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Updates app manager so as to deal with controllers and toolbar"
from typing           import Generic, TypeVar, cast

from bokeh.layouts    import layout, column

from utils.inspection import getclass, templateattribute

TOOLBAR = TypeVar("TOOLBAR")
VIEW    = TypeVar("VIEW")

class _AppName:
    def __get__(self, _, owner):
        cls  = templateattribute(owner, 1)
        assert cls is not None and not isinstance(cls, cast(type, TypeVar))
        return getattr(cls, "APPNAME", cls.__name__.replace('view', ''))

class ViewWithToolbar(Generic[TOOLBAR, VIEW]):
    "A view with the toolbar on top"
    APPNAME = _AppName()
    def __init__(self, ctrl = None, **kwa):
        get = lambda x: cast(type, templateattribute(self, x))
        assert not isinstance(get(0), cast(type, TypeVar))
        self._bar      = get(0)(ctrl = ctrl, **kwa)
        self._mainview = get(1)(ctrl = ctrl, **kwa)

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
    return ToolbarView
