#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"all view aspects here"
from bokeh.models           import Tabs, Panel
from bokeh                  import layouts
from view.base              import BokehView
from view.plots             import PlotState
from cleaning.view          import CleaningView
from qualitycontrol.view    import QualityControlView
from fov                    import FoVPlotView
from cyclesplot             import CyclesPlotView
from .peaksplot             import PeaksPlotView
from ._io                   import setupio

class HybridStatView(BokehView):
    "A view with all plots"
    TASKS = ((lambda lst: tuple(j for i, j in enumerate(lst) if j not in lst[:i]))
             (CleaningView.TASKS+PeaksPlotView.TASKS))
    def __init__(self, **kwa):
        "Sets up the controller"
        super().__init__(**kwa)
        self._tabs   = None
        self._panels = [FoVPlotView         (**kwa),
                        QualityControlView  (**kwa),
                        CleaningView        (**kwa),
                        CyclesPlotView      (**kwa),
                        PeaksPlotView       (**kwa)]

        self._ctrl.getGlobal('css.plot').figure.defaults = dict(sizing_mode = 'fixed')
        self._ctrl.getGlobal('css').hybridstat.defaults  = dict(width = 500, height = 30)
        titles = self._ctrl.getGlobal('css').hybridstat.title
        for panel in self._panels:
            key                         = self.__key(panel)
            titles[key].default         = getattr(panel, 'PANEL_NAME', key.capitalize())
            self.__state(panel).default = PlotState.disabled
        titles['fov'].default           = 'FoV'

        self.__state(self.__select(CleaningView)).default = PlotState.active

    @staticmethod
    def __key(panel):
        return panel.plotter.key().split('.')[-1]

    @staticmethod
    def __state(panel, val = None):
        ret = panel.plotter.project.state
        if val is not None:
            ret.set(PlotState(val))
        return ret

    def __select(self, tpe):
        return next(i for i in self._panels if isinstance(i, tpe))

    def ismain(self):
        "Allows setting-up stuff only when the view is the main one"
        self.__select(CleaningView) .ismain()
        self.__select(PeaksPlotView).ismain()
        self._ctrl.getGlobal('config').tasks.default = self.TASKS
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

        ind = next((i for i, j in enumerate(self._panels)
                    if self.__state(j).get() is PlotState.active),
                   None)
        if ind is None:
            ind = next(i for i, j in enumerate(self._panels)
                       if isinstance(i, CleaningView))

        for panel in self._panels[:ind]:
            self.__state(panel, PlotState.disabled)
        self.__state(self._panels[ind], PlotState.active)
        for panel in self._panels[ind+1:]:
            self.__state(panel, PlotState.disabled)

        mode.update(self._ctrl.getGlobal('css').hybridstat.getitems('width', 'height'))
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
        return layouts.row(layouts.widgetbox(tabs, **mode), **mode)

    def observe(self):
        super().observe()
        def _make(ind):
            def _fcn(val):
                if val.value == PlotState.active and self._tabs is not None:
                    self._tabs.active = ind
            return _fcn

        for ind, panel in enumerate(self._panels):
            self.__state(panel).observe(_make(ind))
