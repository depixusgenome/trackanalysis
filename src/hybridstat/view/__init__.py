#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"all view aspects here"
from bokeh.models   import Tabs, Panel
from bokeh          import layouts
from view.base      import BokehView
from view.plots     import PlotState
from view.beadplot  import BeadPlotView
from cyclesplot     import CyclesPlotView
from .peaksplot     import PeaksPlotView

class HybridStatView(BokehView):
    "A view with all plots"
    def __init__(self, **kwa):
        "Sets up the controller"
        super().__init__(**kwa)
        self._tabs   = None
        self._panels = [BeadPlotView  (**kwa),
                        CyclesPlotView(**kwa),
                        PeaksPlotView (**kwa)]

        titles = self._ctrl.getGlobal('css').hybridstat.title
        for panel in self._panels:
            key                         = self.__key(panel)
            titles[key].default         = key.capitalize()
            self.__state(panel).default = PlotState.disabled

        self.__state(self._panels[1]).default = PlotState.active

    @staticmethod
    def __key(panel):
        return panel.plotter.key().split('.')[-1]

    @staticmethod
    def __state(panel, val = None):
        ret = panel.plotter.project.state
        if val is not None:
            ret.set(PlotState(val))
        return ret

    def ismain(self):
        "Allows setting-up stuff only when the view is the main one"
        self._panels[-1].ismain()
        def _advanced():
            for panel in self._panels:
                if self.__state(panel).get() is PlotState.active:
                    getattr(panel, 'advanced', lambda:None)()
                    break
        self._keys.addKeyPress(('keypress.advanced', _advanced))

    def getroots(self, doc):
        "returns object root"
        titles = self._ctrl.getGlobal('css').hybridstat.title
        mode   = self.defaultsizingmode()
        def _panel(view):
            ret = view.getroots(doc)
            while isinstance(ret, (tuple, list)) and len(ret) == 1:
                ret = ret[0]
            if isinstance(ret, (tuple, list)):
                ret = layouts.column(ret, **mode)
            return Panel(title = titles[self.__key(view)].get(), child = ret, **mode)

        ind  = next((i for i, j in enumerate(self._panels)
                     if self.__state(j).get() is PlotState.active),
                    1)

        for panel in self._panels[:ind]:
            self.__state(panel, PlotState.disabled)
        self.__state(self._panels[ind], PlotState.active)
        for panel in self._panels[ind+1:]:
            self.__state(panel, PlotState.disabled)

        tabs = Tabs(tabs   = [_panel(panel) for panel in self._panels],
                    active = ind,
                    name   = 'Hybridstat:Tabs',
                    **mode)

        @self.action
        def _py_cb(attr, old, new):
            self._panels[old].activate(False)
            self._panels[new].activate(True)
            self._ctrl.handle('undoaction',
                              self._ctrl.outastuple,
                              (lambda: setattr(self._tabs, 'active', old),))
        tabs.on_change('active', _py_cb)
        self._tabs = tabs
        return layouts.widgetbox(tabs, **mode)

    def observe(self):
        super().observe()
        def _make(ind):
            def _fcn(val):
                if val.value == PlotState.active and self._tabs is not None:
                    self._tabs.active = ind
            return _fcn

        for ind, panel in enumerate(self._panels):
            self.__state(panel).observe(_make(ind))
