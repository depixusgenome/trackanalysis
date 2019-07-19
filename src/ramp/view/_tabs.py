#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"all view aspects here"
from typing                 import Set, Dict

from control.decentralized  import Indirection
from fov                    import BaseFoVPlotCreator, FoVPlotModel
from view.plots             import PlotView
from taskview.tabs          import TabsView, TabsTheme, initsubclass
from cleaning.view          import CleaningPlotCreator,  CleaningWidgets
from ._plot                 import RampPlotView
from ._model                import RampTaskPlotModelAccess, RampPlotDisplay

class FoVPlotCreator(BaseFoVPlotCreator[RampTaskPlotModelAccess, # type: ignore
                                        FoVPlotModel]):
    "Plots a default bead and its FoV"
    _plotmodel: FoVPlotModel
    _model:     RampTaskPlotModelAccess
    _rampdisplay = Indirection()
    def observe(self, ctrl, noerase = True):
        "sets-up model observers"
        super().observe(ctrl, noerase = noerase)
        self._rampdisplay = RampPlotDisplay()

        @ctrl.display.observe(self._rampdisplay)
        def _ondataframes(old = (), **_):
            if len({"dataframe", "consensus"} & set(old)):
                self.reset(False)

    def _tooltips(self):
        return self._oktooltips({})

    def _status(self) -> Dict[str, Set[int]]:
        return self._rampdisplay.status(self._model.roottask, self._ctrl)

class FoVPlotView(PlotView[FoVPlotCreator]):
    "FoV plot view"

class RampCleaningPlotCreator(CleaningPlotCreator):
    "cleaning for ramps"
    def __init__(self, ctrl):
        super().__init__(ctrl, text = '\n'.join(CleaningWidgets.text(None).split('\n')[:-2]))

class CleaningView(PlotView[RampCleaningPlotCreator]):
    "Peaks plot view"
    TASKS = 'aberrant', 'datacleaning', 'extremumalignment'
    def ismain(self, ctrl):
        "Cleaning and alignment, ... are set-up by default"
        self._ismain(ctrl, tasks  = self.TASKS)

PANELS = {FoVPlotView: 'fov', CleaningView: 'cleaning', RampPlotView: 'ramp'}

class RampTabTheme(TabsTheme):
    "Ramps tab theme"
    def __init__(self):
        super().__init__("ramp", PANELS)

@initsubclass("Ramps:Tabs", PANELS, (RampPlotView,))
class RampView(TabsView[RampTabTheme]):
    "view of ramps & FoV"
    APPNAME = "RampApp"
