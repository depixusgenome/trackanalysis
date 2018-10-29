#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"all view aspects here"
from typing              import Set

from fov                 import BaseFoVPlotCreator, FoVPlotModel
from view.plots          import PlotView
from view.tabs           import TabsView, TabsTheme, initsubclass
from ._plot              import RampPlotView
from ._model             import RampTaskPlotModelAccess, RampPlotDisplay

class RampTabTheme(TabsTheme):
    "HybridStatTheme"
    name:    str = "ramp.tab"
    initial: str = "ramp"

class FoVPlotCreator(BaseFoVPlotCreator[RampTaskPlotModelAccess, # type: ignore
                                        FoVPlotModel]):
    "Plots a default bead and its FoV"
    def __init__(self,  ctrl):
        "sets up this plotter's info"
        self._rampdisplay = RampPlotDisplay()
        super().__init__(ctrl)

    def observe(self, ctrl):
        "sets-up model observers"
        super().observe(ctrl)

        @ctrl.display.observe(self._rampdisplay)
        def _ondataframes(old = (), **_):
            if len({"dataframe", "consensus"} & set(old)):
                self.reset(False)

    def addto(self, ctrl, noerase = True):
        "adds the models to the controller"
        super().addto(ctrl, noerase)
        self._rampdisplay = ctrl.display.add(self._rampdisplay, noerase = noerase)

    def _tooltips(self):
        return self._goodtooltips({})

    def _availablefixedbeads(self) -> Set[int]:
        data = self._rampdisplay.dataframe.get(self._model.roottask, None)
        return set() if data is None else set(data[data.status == "fixed"].bead.unique())

    def _badbeads(self) -> Set[int]:
        data = self._rampdisplay.dataframe.get(self._model.roottask, None)
        return set() if data is None else set(data[data.status == "bad"].bead.unique())

class FoVPlotView(PlotView[FoVPlotCreator]):
    "FoV plot view"
    TASKS = ()
    def ismain(self, ctrl):
        "Cleaning is set up by default"
        self._ismain(ctrl, tasks = self.TASKS)

@initsubclass("Ramps:Tabs",
              {FoVPlotView: 'fov', RampPlotView: 'ramp'},
              (RampPlotView,))
class RampView(TabsView[RampTabTheme]):
    "view of ramps & FoV"
