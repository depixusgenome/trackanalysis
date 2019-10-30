#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Main view"
from typing          import Any
from bokeh           import layouts
from view.base       import BokehView, stretchout
from view.threaded   import DisplayState
from utils.logconfig import getLogger
from ._beadsplot     import BeadsScatterPlot
from ._statsplot     import FoVStatsPlot
from ._widgets       import JobsStatusBar, PeakcallingPlotWidget
from ._threader      import ismain

LOGS = getLogger(__name__)

class _StateDescriptor:
    @staticmethod
    def __elems(inst):
        ctrl = getattr(inst, '_ctrl').display
        mdl  = getattr(inst, '_plotmodel').display.name
        return ctrl, mdl

    def __get__(self, inst, owner):
        return self if inst is None else getattr(getattr(inst, '_items')[0], '_state')

    @classmethod
    def setdefault(cls, inst, value):
        "sets the default value"
        for i in getattr(inst, '_items'):
            if hasattr(i, '_state'):
                setattr(i, '_state', value)

    def __set__(self, inst, value):
        self.setdefault(inst, value)

class FoVPeakCallingView(BokehView):
    "Shows beads & stats"
    _ctrl: Any
    PANEL_NAME  = 'Statistics'

    def __init__(self, ctrl = None, **kwa):
        super().__init__(ctrl, **kwa)
        self._items = [
            BeadsScatterPlot(widgets = False),
            FoVStatsPlot(widgets = False),
            PeakcallingPlotWidget(),
            JobsStatusBar(),
        ]

    @property
    def plotter(self):
        "needed for adding to tabs"
        return self

    state = _StateDescriptor()

    def swapmodels(self, ctrl):
        "swap models"
        for i in self._items:
            if hasattr(i, 'swapmodels'):
                i.swapmodels(ctrl)

    def activate(self, val):
        "activates the component: resets can occur"
        old        = self.state
        self.state = DisplayState.active if val else DisplayState.disabled
        if val and (old is DisplayState.outofdate) and hasattr(self, '_ctrl'):
            self.reset(self._ctrl)

    def reset(self, *_):
        "resets"
        for i in self._items:
            if hasattr(i, 'reset'):
                try:
                    i.reset(self._ctrl)
                except Exception as exc:  # pylint: disable=broad-except
                    LOGS.exception(exc)

    def observe(self, ctrl):
        """observe the controller"""
        self._ctrl = ctrl
        self._items[0].observe(ctrl)
        self._items[1].observe(ctrl)
        self._items[3].observe(ctrl, getattr(self._items[0], '_model').tasks)

    def isactive(self, *_1, **_2) -> bool:
        "whether the state is set to active"
        return self.state == DisplayState.active

    def addtodoc(self, ctrl, doc):
        "sets the plot up"
        itms   = [i.addtodoc(ctrl, doc)[0] for i in self._items]
        mode   = self.defaultsizingmode()
        sizes  = self.defaulttabsize(ctrl)
        brds   = ctrl.theme.get("main", "borders", 5)
        itms[0].update(
            plot_width  = sizes['width'],
            plot_height = int(
                sizes['height'] * (
                    itms[0].plot_height / (sum(i.plot_height for i in itms[:2]) + brds)
                )
            )
        )
        itms[1].update(
            plot_width  = sizes['width'] - brds - max(i.width for i in itms[2:]),
            plot_height = sizes['height'] - brds - itms[0].plot_height
        )
        return stretchout(layouts.column(
            [
                itms[0],
                layouts.row(
                    [
                        itms[1],
                        layouts.widgetbox(
                            itms[2:],
                            width  = max(i.width    for i in itms[2:]),
                            height = sum(i.height   for i in itms[2:])
                        )
                    ],
                    **dict(sizes,  height = itms[1].plot_height, **mode)
                ),
            ],
            **sizes, **mode
        ))

    ismain = staticmethod(ismain)
