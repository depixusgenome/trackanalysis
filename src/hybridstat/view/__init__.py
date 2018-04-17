#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"all view aspects here"
from bokeh.models           import Tabs, Panel, Spacer
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
    def __init__(self, ctrl = None, **kwa):
        "Sets up the controller"
        super().__init__(ctrl = ctrl, **kwa)
        self._tabs   = None
        self._roots  = [] # type: ignore
        self._panels = [FoVPlotView         (ctrl = ctrl, **kwa),
                        QualityControlView  (ctrl = ctrl, **kwa),
                        CleaningView        (ctrl = ctrl, **kwa),
                        CyclesPlotView      (ctrl = ctrl, **kwa),
                        PeaksPlotView       (ctrl = ctrl, **kwa)]

        ctrl.globals.css.plot.figure.defaults = dict(sizing_mode = 'fixed')
        ctrl.globals.css.hybridstat.defaults  = dict(width = 500, height = 60)
        titles = ctrl.globals.css.hybridstat.title
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

    def ismain(self, ctrl):
        "Allows setting-up stuff only when the view is the main one"
        self.__select(CleaningView) .ismain(ctrl)
        self.__select(PeaksPlotView).ismain(ctrl)
        ctrl.globals.config.tasks.default = self.TASKS
        def _advanced():
            for panel in self._panels:
                if self.__state(panel).get() is PlotState.active:
                    getattr(panel, 'advanced', lambda:None)()
                    break
        ctrl.display.updatedefaults('keystroke', advanced = _advanced)

    def addtodoc(self, ctrl, doc):
        "returns object root"
        super().addtodoc(ctrl, doc)

        titles = ctrl.globals.css.hybridstat.title
        mode   = self.defaultsizingmode()
        def _panel(view):
            ret = view.addtodoc(ctrl, doc)
            while isinstance(ret, (tuple, list)) and len(ret) == 1:
                ret = ret[0]
            if isinstance(ret, (tuple, list)):
                ret = layouts.column(ret, **mode)
            self._roots.append(ret)
            return Panel(title = titles[self.__key(view)].get(), child = Spacer(), **mode)

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

        mode.update(ctrl.globals.css.hybridstat.getitems('width', 'height'))
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
        def _make(ind):
            def _fcn(val):
                if val.value == PlotState.active and self._tabs is not None:
                    self._tabs.active = ind
            return _fcn

        for ind, panel in enumerate(self._panels):
            self.__state(panel).observe(_make(ind))
