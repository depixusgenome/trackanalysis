#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"all view aspects here"
from typing                 import Set, Dict

from control.decentralized  import Indirection
from fov                    import BaseFoVPlotCreator, FoVPlotModel
from view.plots             import PlotView
from taskview.tabs          import TabsView, TabsTheme, initsubclass
from cleaning.view          import CleaningPlotCreator,  CleaningWidgets, DataCleaningModelAccess
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

class RampDataCleaningModelAccess(DataCleaningModelAccess):
    "ramp data cleaning model access"
    def addto(self, ctrl, noerase = False):
        "add to the controller"

    @property
    def availablefixedbeads(self):
        "returns bead ids for potential fixed beads"
        return []

class RampCleaningPlotCreator(CleaningPlotCreator):
    "cleaning for ramps"
    def __init__(self, ctrl):
        txt = CleaningWidgets.text(None).split('\n')
        txt = txt[next((i for i, j in enumerate(txt) if '## Cleaning' in j), 0):]
        txt = [i for i in txt if '(clipping.' not in i]
        model = RampDataCleaningModelAccess(ctrl)
        super().__init__(ctrl, model = model, text = '\n'.join(txt))

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
