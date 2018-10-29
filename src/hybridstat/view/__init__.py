#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"all view aspects here"
from collections         import OrderedDict
from typing              import Dict

from bokeh               import layouts
from bokeh.models        import Panel, Spacer, Tabs

from cleaning.view       import CleaningView
from cyclesplot          import CyclesPlotView
from fov                 import FoVPlotView
from model.plots         import PlotState
from qualitycontrol.view import QualityControlView
from view.base           import BokehView

from ._io                import setupio
from .peaksplot          import PeaksPlotView

class HybridStatTheme:
    "HybridStatTheme"
    name                   = "hybridstat"
    width                  = 500
    height                 = 60
    initial                = "cleaning"
    titles: Dict[str, str] = {}

class HybridStatView(BokehView):
    "A view with all plots"
    KEYS : Dict[type, str]   = OrderedDict()
    KEYS[FoVPlotView]        = 'fov'
    KEYS[QualityControlView] = 'qc'
    KEYS[CleaningView]       = 'cleaning'
    KEYS[CyclesPlotView]     = 'cycles'
    KEYS[PeaksPlotView]      = 'peaks'
    TASKS_CLASSES            = (CleaningView, PeaksPlotView)
    TASKS = ((lambda lst: tuple(j for i, j in enumerate(lst) if j not in lst[:i]))
             (sum((list(i.TASKS) for i in TASKS_CLASSES), []))) # type: ignore
    def __init__(self, ctrl = None, **kwa):
        "Sets up the controller"
        super().__init__(ctrl = ctrl, **kwa)
        self._tabs   = None
        self._roots  = [] # type: ignore
        self.__theme = ctrl.theme.add(HybridStatTheme())
        self._panels = [cls(ctrl, **kwa) for cls in self.KEYS]

        for panel in self._panels:
            key                      = self.__key(panel)
            self.__theme.titles[key] = getattr(panel, 'PANEL_NAME', key.capitalize())
        self.__theme.titles['fov']   = 'FoV'

        cur = self.__select(self.__initial())
        for panel in self._panels:
            desc = type(panel.plotter).state
            desc.setdefault(panel.plotter, (PlotState.active if panel is cur else
                                            PlotState.disabled))


    def __initial(self):
        "return the initial tab"
        return next(i for i, j in self.KEYS.items() if j == self.__theme.initial)

    @classmethod
    def __key(cls, panel):
        return cls.KEYS[type(panel)]

    @staticmethod
    def __state(panel, val = None):
        if val is not None:
            panel.plotter.state = PlotState(val)
        return panel.plotter.state

    def __select(self, tpe):
        return next(i for i in self._panels if isinstance(i, tpe))

    def ismain(self, ctrl):
        "Allows setting-up stuff only when the view is the main one"
        for i in self.TASKS_CLASSES:
            self.__select(i).ismain(ctrl)
        ctrl.theme.updatedefaults("tasks.io", tasks = self.TASKS)
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
            cur = self.__initial()
            ind = next(i for i, j in enumerate(self._panels) if isinstance(i, cur))

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

        @ctrl.action
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
        for panel in self._panels:
            panel.observe(ctrl)
