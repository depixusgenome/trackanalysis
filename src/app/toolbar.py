#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Updates app manager so as to deal with controllers and toolbar"
from typing           import cast
from utils.inspection import getclass
from .launcher        import setup
from .maincontrol     import createview
from .default         import VIEWS, CONTROLS

class WithToolbar:
    "Creates an app with a toolbar"
    TBAR = "view.toolbar.BeadToolbar"
    def __init__(self, tbar = None):
        self.tbar = tbar

    def __call__(self, main):
        if self.tbar is None:
            from view.toolbar import BeadToolbar
            tbar = cast(type, BeadToolbar)
        else:
            tbar = cast(type, getclass(self.tbar))

        from bokeh.layouts  import layout, column
        from view           import BokehView
        class ViewWithToolbar(BokehView):
            "A view with the toolbar on top"
            APPNAME = getattr(main, 'APPNAME', main.__name__.lower().replace('view', ''))
            def __init__(self, **kwa):
                self._bar      = tbar(**kwa)
                self._mainview = main(**kwa)
                super().__init__(**kwa)

            def ismain(self):
                "sets-up the main view as main"
                self._mainview.ismain()

            def close(self):
                "remove controller"
                super().close()
                self._bar.close()
                self._mainview.close()

            def getroots(self, doc):
                "adds items to doc"
                tbar   = self._bar.getroots(doc)
                others = self._mainview.getroots(doc)
                mode   = self.defaultsizingmode()
                while isinstance(others, (tuple, list)) and len(others) == 1:
                    others = others[0]

                if isinstance(others, list):
                    children = [tbar] + others
                elif isinstance(others, tuple):
                    children = [tbar, layout(others, **mode)]
                else:
                    children = [tbar, others]

                return column(children, **mode)

        return ViewWithToolbar

setup(locals(),
      creator         = lambda i, j, k: createview(WithToolbar()(i), j, k),
      defaultcontrols = CONTROLS,
      defaultviews    = VIEWS+(WithToolbar.TBAR,))
