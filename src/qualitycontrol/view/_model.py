#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"View module showing all messages concerning discarded beads"
from   typing               import List, Dict, Set
import numpy                as     np

from   data                 import BEADKEY
from   control.modelaccess  import TaskPlotModelAccess, TaskAccess
from   cleaning.processor   import (DataCleaningTask, # pylint: disable=unused-import
                                    DataCleaningProcessor)
from   model.level          import PHASE
from   model.plots          import PlotAttrs, PlotTheme, PlotModel, PlotDisplay
from   utils                import initdefaults

class GuiDataCleaningProcessor(DataCleaningProcessor):
    "gui data cleaning processor"
    @classmethod
    def compute(cls, frame, info, cache = None, **cnf):
        "returns the result of the beadselection"
        err = super().compute(frame, info, cache = cache, **cnf)
        if err:
            cache.setdefault('messages', []).extend([(info[0],)+ i for i in err.args[0].data()])
        return None

class DataCleaningTaskAccess(TaskAccess, tasktype = DataCleaningTask):
    "access to the DataCleaningTask"

class QualityControlDisplay:
    "QualityControlDisplay"
    name                      = "qc"
    messages: Dict[str, list] = {}
    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        pass

class QualityControlConfig:
    "QualityControlDisplay"
    name            = "qc"
    fixedbeadextent = .2
    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        pass


    def fixedbeads(self, ctrl, root) -> Set[BEADKEY]:
        "returns bead ids with extent == all cycles"
        lst   = ctrl.tasklist(root)
        if not lst:
            return set()

        clean = next((t for t in lst if isinstance(t, DataCleaningTask)), None)
        if not clean:
            return set()

        cache = ctrl.cache(root, clean)()
        if cache is None:
            return set()

        minext = self.fixedbeadextent
        def _compute(itm):
            arr   = next((i.values for i in itm if i.name == 'extent'), None)
            if arr is None:
                return False

            valid = np.isfinite(arr)
            return np.sum(arr[valid] < minext) == np.sum(valid)

        return set(i for i, (j, _) in cache.items() if _compute(j))

class QualityControlModelAccess(TaskPlotModelAccess):
    "access to data cleaning"
    def __init__(self, ctrl) -> None:
        super().__init__(ctrl)
        self.cleaning  = DataCleaningTaskAccess(self)
        self.__config  = ctrl.theme.add(QualityControlConfig(),    False)
        self.__display = ctrl.display.add(QualityControlDisplay(), False)

    def buildmessages(self):
        "creates beads and warnings where applicable"
        default = dict.fromkeys(('type', 'message', 'bead', 'cycles'), []) # type: Dict[str, List]
        tsk     = self.cleaning.task
        if tsk is not None:
            ctx = self.runcontext(GuiDataCleaningProcessor)
            with ctx as view:
                if view is not None:
                    for _ in view:
                        pass

                mem = ctx.taskcache(tsk).pop('messages', None)
                if mem:
                    default = dict(bead    = [i[0] for i in mem],
                                   cycles  = [i[1] for i in mem],
                                   type    = [i[2] for i in mem],
                                   message = [i[3] for i in mem])
        self._ctrl.display.update(self.__display, messages = default)

    def badbeads(self) -> Set[BEADKEY]:
        "returns bead ids with messages"
        if self.track is None:
            return set()
        return set(self.messages()['bead'])

    def fixedbeads(self) -> Set[BEADKEY]:
        "returns bead ids with extent == all cycles"
        return self.__config.fixedbeads(self._ctrl.tasks, self.roottask)

    def messages(self) -> Dict[str, List]:
        "returns beads and warnings where applicable"
        msg = self.__display.messages
        if not msg:
            self.buildmessages()
        return self.__display.messages

    def clear(self):
        "clears the model's cache"
        self._ctrl.display.update(self.__display, messages = {})

class DriftControlPlotTheme(PlotTheme):
    "drift control plot theme"
    name             = "qc.driftcontrol.plot"
    measures         = PlotAttrs('lightblue',  'line', 2, alpha     = .75)
    median           = PlotAttrs('lightgreen', 'line', 2, line_dash = 'dashed')
    pop10            = PlotAttrs('lightgreen', 'line', 2, line_dash = [4])
    pop90            = PlotAttrs('lightgreen', 'line', 2, line_dash = [4])
    figsize          = 700, 150, 'fixed'
    outlinewidth     = 7
    outlinecolor     = 'red'
    outlinealpha     = .5
    ylabel           = ''
    xlabel           = 'Cycles'
    toolbar          = dict(PlotTheme.toolbar)
    toolbar['items'] = 'pan,box_zoom,reset,save'

    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        super().__init__(**_)

class DriftControlPlotConfig:
    "allows configuring the drift control plots"
    name              = "qc.driftcontrol"
    percentiles       = [10, 50, 90]
    yspan             = [5, 95], 0.3
    phases            = PHASE.initial, PHASE.pull
    warningthreshold  = 0.3

    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        pass

class DriftControlPlotModel(PlotModel):
    "qc plot model"
    theme   = DriftControlPlotTheme()
    config  = DriftControlPlotConfig()
    display = PlotDisplay(name = "qc")

class ExtensionPlotConfig(DriftControlPlotConfig):
    "allows configuring the drift control plots"
    name              = "qc.extension"
    ybarspercentiles  = [25, 75]
    yspan             = [5, 95], 0.3
    phases            = PHASE.initial, PHASE.pull
    warningthreshold  = 1.5e-2
    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        super().__init__(**_)

class ExtensionPlotTheme(DriftControlPlotTheme):
    "drift control plot theme"
    name       = "qc.extension.plot"
    ylabel     = 'δ(Φ3-Φ1) (µm)'
    measures   = PlotAttrs('lightblue', 'circle', 2, alpha = .75)
    ybars      = PlotAttrs('lightblue', 'vbar', 1,   alpha = .75)
    ymed       = PlotAttrs('lightblue', 'vbar', 1,   fill_alpha = 0.)
    ybarswidth = .8
    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        super().__init__(**_)
