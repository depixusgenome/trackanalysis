#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"View module showing all messages concerning discarded beads"
from   typing                   import List, Dict, Set, Tuple, Iterator

from   data                     import BEADKEY
from   control.modelaccess      import TaskPlotModelAccess, TaskAccess
from   cleaning.view            import FixedBeadDetectionModel, FIXED_LIST
from   cleaning.processor       import (DataCleaningTask, # pylint: disable=unused-import
                                        DataCleaningProcessor)
from   model.level              import PHASE
from   model.plots              import PlotAttrs, PlotTheme, PlotModel, PlotDisplay
from   utils                    import dataclass, dflt, field, initdefaults

class GuiDataCleaningProcessor(DataCleaningProcessor):
    "gui data cleaning processor"
    @classmethod
    def compute(cls, frame, info, cache = None, **cnf):
        "returns the result of the beadselection"
        err = super().compute(frame, info, cache = cache, **cnf)
        if err:
            # pylint: disable=unsubscriptable-object
            lst = [(info[0],)+ i for i in err.args[0].data()]
            cache.setdefault('messages', []).extend(lst)

class DataCleaningTaskAccess(TaskAccess, tasktype = DataCleaningTask):
    "access to the DataCleaningTask"

@dataclass
class MissinBeadDetectionConfig:
    "filters on messages to reinterpret these as missing beads"
    hfsigma    = 90
    population = 90
    pingpong   = 10
    def filter(self, ncycles, msgs) -> Iterator[int]:
        "filter messages to return missing beads"
        vals = {i: getattr(self, i) * ncycles*1e-2
                for i in ("hfsigma", "population", "pingpong")}
        return (i for i, j, k in zip(msgs["bead"], msgs["type"], msgs["cycles"])
                if vals.get(j, ncycles+1) <= k)

@dataclass
class QualityControlDisplay:
    "QualityControlDisplay"
    name:     str             = "qc"
    messages: Dict[str, list] = field(default_factory = dict)

class QualityControlModelAccess(TaskPlotModelAccess):
    "access to data cleaning"
    def __init__(self, ctrl) -> None:
        super().__init__(ctrl)
        self.cleaning  = DataCleaningTaskAccess(self)
        self.__config  = FixedBeadDetectionModel(ctrl)
        self.__missing = ctrl.theme.add(MissinBeadDetectionConfig(), False)
        self.__display = ctrl.display.add(QualityControlDisplay(), False)

    def addto(self, ctrl, name = "tasks", noerase = False):
        "set _tasksmodel to same as main"
        super().addto(ctrl, name, noerase)
        self.__config.addto(ctrl, noerase)

    def buildmessages(self):
        "creates beads and warnings where applicable"
        default: Dict[str, List] = dict.fromkeys(('type', 'message', 'bead', 'cycles'), [])
        tsk = self.cleaning.task
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

    def availablefixedbeads(self) -> FIXED_LIST:
        "returns bead ids with extent == all cycles"
        if self.roottask is None:
            return []
        return self.__config.current(self._ctrl, self.roottask)

    def messages(self) -> Dict[str, List]:
        "returns beads and warnings where applicable"
        msg = self.__display.messages
        if not msg:
            self.buildmessages()
        return self.__display.messages

    def status(self) -> Dict[str, Set[int]]:
        "returns beads and warnings where applicable"
        if self.track is None:
            return {i: set() for i in ('bad', 'ok', 'fixed', 'missing')}

        msg  = self.messages()
        data = {'bad':     set(msg["bead"]),
                'fixed':   set(i[-1] for i in self.availablefixedbeads()),
                'ok':      set(self.track.beads.keys()),
                'missing': set(self.__missing.filter(self.track.ncycles, msg))}

        for i, j in data.items():
            if i != "ok":
                data['ok'].symmetric_difference_update(j)
                if i != "bad":
                    data['bad'].symmetric_difference_update(j)
        return data

    def clear(self):
        "clears the model's cache"
        self._ctrl.display.update(self.__display, messages = {})

class DriftControlPlotTheme(PlotTheme):
    "drift control plot theme"
    name             = "qc.driftcontrol.plot"
    measures         = PlotAttrs('', 'line', 2, alpha     = .75)
    median           = PlotAttrs('', 'line', 2, line_dash = 'dashed')
    pop10            = PlotAttrs('', 'line', 2, line_dash = [4])
    pop90            = PlotAttrs('', 'line', 2, line_dash = [4])
    colors           = dict(dark  = dict(measures = 'lightblue',
                                         median   = 'lightgreen',
                                         pop10    = 'lightgreen',
                                         pop90    = 'lightgreen'),
                            basic = dict(measures = 'darkblue',
                                         median   = 'darkgreen',
                                         pop10    = 'darkgreen',
                                         pop90    = 'darkgreen'))
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

@dataclass
class DriftControlPlotConfig:
    "allows configuring the drift control plots"
    name             : str                     = "qc.driftcontrol"
    percentiles      : List[int]               = dflt([10, 50, 90])
    yspan            : Tuple[List[int], float] = dflt(([5, 95], 0.3))
    phases           : Tuple[int, int]         = (PHASE.initial, PHASE.pull)
    warningthreshold : float                   = 0.3

class DriftControlPlotModel(PlotModel):
    "qc plot model"
    theme   = DriftControlPlotTheme()
    config  = DriftControlPlotConfig()
    display = PlotDisplay(name = "qc")
    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        super().__init__()

@dataclass
class ExtensionPlotConfig(DriftControlPlotConfig):
    "allows configuring the drift control plots"
    name             : str       = "qc.extension"
    ybarspercentiles : List[int] = dflt([25, 75])
    warningthreshold : float     = 1.5e-2

class ExtensionPlotTheme(DriftControlPlotTheme):
    "drift control plot theme"
    name       = "qc.extension.plot"
    ylabel     = 'δ(Φ3-Φ1) (µm)'
    measures   = PlotAttrs('', 'circle', 2, alpha = .75)
    ybars      = PlotAttrs('', 'vbar', 1,   alpha = .75)
    ymed       = PlotAttrs('', 'vbar', 1,   fill_alpha = 0.)
    colors     = dict(DriftControlPlotTheme.colors)
    colors['dark'] .update(ybars = 'lightblue', ymed = 'lightblue')
    colors['basic'].update(ybars = 'darkblue',  ymed = 'darkblue')
    ybarswidth = .8
    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        super().__init__(**_)
