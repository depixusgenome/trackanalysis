#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"all view aspects here"
from typing                 import Dict
from functools              import partial
from bokeh.models           import Tabs, Panel, Spacer
from bokeh                  import layouts
from view.base              import BokehView
from model.plots            import PlotState
from cleaning.view          import CleaningView
from qualitycontrol.view    import QualityControlView
from fov                    import FoVPlotView
from cyclesplot             import CyclesPlotView
from .peaksplot             import PeaksPlotView
from ._io                   import setupio

class HybridStatTheme:
    "HybridStatTheme"
    width                  = 500
    height                 = 60
    titles: Dict[str, str] = {}

class HybridStatView(BokehView):
    "A view with all plots"
    TASKS = ((lambda lst: tuple(j for i, j in enumerate(lst) if j not in lst[:i]))
             (CleaningView.TASKS+PeaksPlotView.TASKS))
    def __init__(self, ctrl = None, **kwa):
        "Sets up the controller"
        super().__init__(ctrl = ctrl, **kwa)
        self._tabs   = None
        self._roots  = [] # type: ignore
        self.__theme = HybridStatTheme()
        self._panels = [FoVPlotView         (ctrl = ctrl, **kwa),
                        QualityControlView  (ctrl = ctrl, **kwa),
                        CleaningView        (ctrl = ctrl, **kwa),
                        CyclesPlotView      (ctrl = ctrl, **kwa),
                        PeaksPlotView       (ctrl = ctrl, **kwa)]

        titles = self.__theme.titles
        for panel in self._panels:
            key         = self.__key(panel)
            titles[key] = getattr(panel, 'PANEL_NAME', key.capitalize())
        titles['fov']   = 'FoV'

        cur = self.__select(CleaningView)
        for panel in self._panels:
            desc = type(panel.plotter).state
            desc.setdefault(panel.plotter, (PlotState.active if panel is cur else
                                            PlotState.disabled))

    @staticmethod
    def __key(panel):
        return panel.plotter.key().split('.')[-1]

    @staticmethod
    def __state(panel, val = None):
        if val is not None:
            panel.plotter.state = PlotState(val)
        return panel.plotter.state

    def __select(self, tpe):
        return next(i for i in self._panels if isinstance(i, tpe))

    def ismain(self, ctrl):
        "Allows setting-up stuff only when the view is the main one"
        self.__select(CleaningView) .ismain(ctrl)
        self.__select(PeaksPlotView).ismain(ctrl)
        ctrl.theme.updatedefaults("taskio", tasks = self.TASKS)
        def _advanced():
            for panel in self._panels:
                if self.__state(panel) is PlotState.active:
                    getattr(panel, 'advanced', lambda:None)()
                    break
        ctrl.display.updatedefaults('keystroke', advanced = _advanced)

    def addtodoc(self, ctrl, doc):
        "returns object root"
        super().addtodoc(ctrl, doc)

        titles = self.__theme.titles
        mode   = self.defaultsizingmode()
        def _panel(view):
            ret = view.addtodoc(ctrl, doc)
            while isinstance(ret, (tuple, list)) and len(ret) == 1:
                ret = ret[0]
            if isinstance(ret, (tuple, list)):
                ret = layouts.column(ret, **mode)
            self._roots.append(ret)
            return Panel(title = titles[self.__key(view)], child = Spacer(), **mode)

        ind = next((i for i, j in enumerate(self._panels)
                    if self.__state(j) is PlotState.active),
                   None)
        if ind is None:
            ind = next(i for i, j in enumerate(self._panels)
                       if isinstance(i, CleaningView))

        for panel in self._panels[:ind]:
            self.__state(panel, PlotState.disabled)
        self.__state(self._panels[ind], PlotState.active)
        for panel in self._panels[ind+1:]:
            self.__state(panel, PlotState.disabled)

        mode.update(width = self.__theme.width, height = self.__theme.height)
        tabs = Tabs(tabs   = [_panel(panel) for panel in self._panels],
                    active = ind,
                    name   = 'Hybridstat:Tabs',
                    **mode)

        @ctrl.display.observe
        def _onapplicationstarted():
            doc.add_root(self._roots[ind])

        @self.action
        def _py_cb(attr, old, new):
            self._panels[old].activate(False)
            doc.remove_root(self._roots[old])
            self._panels[new].activate(True)
            doc.add_root(self._roots[new])
            ctrl.undos.handle('undoaction',
                              ctrl.emitpolicy.outastuple,
                              (lambda: setattr(self._tabs, 'active', old),))
        tabs.on_change('active', _py_cb)
        self._tabs = tabs
        return layouts.row(layouts.widgetbox(tabs, **mode), **mode)

    def observe(self, ctrl):
        "observing the controller"
        super().observe(ctrl)
        def _fcn(ind, panel, old = None, **_):
            if 'state' not in old:
                return
            if panel.state == PlotState.active and self._tabs is not None:
                self._tabs.active = ind

        for ind, panel in enumerate(self._panels):
            panel.observe(ctrl)
            ctrl.display.observe(getattr(panel, '_display'), partial(_fcn, ind, panel))
