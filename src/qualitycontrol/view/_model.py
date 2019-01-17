#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"View module showing all messages concerning discarded beads"
from   functools                import partial
from   typing                   import List, Dict, Set, Tuple, Iterator

from   data                     import BEADKEY
from   control.decentralized    import Indirection
from   cleaning.view            import DataCleaningModelAccess
from   cleaning.processor       import (DataCleaningProcessor, ClippingProcessor,
                                        ClippingTask)
from   model.plots              import PlotAttrs, PlotTheme, PlotModel, PlotDisplay
from   taskmodel                import PHASE
from   taskcontrol.beadscontrol import DataSelectionBeadController
from   utils                    import initdefaults

# pylint: disable=unused-import,wrong-import-order,ungrouped-imports
from   cleaning.processor.__config__ import DataCleaningTask

def _extend(cache, info, exc):
    if exc:
        lst = [(info[0],)+ i for i in exc.args[0].data()]
        cache.setdefault('messages', []).extend(lst)

class GuiClippingProcessor(ClippingProcessor):
    "gui data cleaning processor"
    @classmethod
    def _cache_action(cls, cache, task, frame, info):
        task(frame.track, *info)
        if task.minpopulation > 0.:
            _extend(cache, info, cls.test(task, frame, info))
        return info

    @classmethod
    def apply(cls, toframe = None, **cnf):
        "applies the task to a frame or returns a method that will"
        if toframe is None:
            return partial(cls.apply, **cnf)
        cache = cnf.pop('cache')
        return toframe.withaction(partial(cls._cache_action, cache, ClippingTask(**cnf)))

    def run(self, args):
        "updates the frames"
        cache = args.data.setcachedefault(self, dict())
        return args.apply(partial(self.apply, cache = cache, **self.config()))

class GuiDataCleaningProcessor(DataCleaningProcessor):
    "gui data cleaning processor"
    @classmethod
    def compute(cls, frame, info, cache = None, **cnf):
        "returns the result of the beadselection"
        _extend(cache, info, super().compute(frame, info, cache = cache, **cnf))

class MissinBeadDetectionConfig:
    "filters on messages to reinterpret these as missing beads"
    def __init__(self):
        self.name:       str = "qc.missing"
        self.hfsigma:    int = 90
        self.population: int = 90
        self.pingpong:   int = 10

    def filter(self, ncycles, msgs) -> Iterator[int]:
        "filter messages to return missing beads"
        vals = {i: getattr(self, i) * ncycles*1e-2
                for i in ("hfsigma", "population", "pingpong")}
        return (i for i, j, k in zip(msgs["bead"], msgs["type"], msgs["cycles"])
                if k is None or (vals.get(j, ncycles+1) <= k))

class QualityControlDisplay:
    "QualityControlDisplay"
    def __init__(self):
        self.name:     str             = "qc"
        self.messages: Dict[str, list] = {}

class QualityControlModelAccess(DataCleaningModelAccess):
    "access to data cleaning"
    __missing = Indirection()
    __display = Indirection()
    def __init__(self, ctrl) -> None:
        super().__init__(ctrl)
        self.__missing = MissinBeadDetectionConfig()
        self.__display = QualityControlDisplay()

    def addto(self, ctrl, noerase = False):
        "set models to same as main"
        super().addto(ctrl, noerase = noerase)
        ctrl.tasks.observe("addtask", "updatetask", "removetask", self._ontask)

    def buildmessages(self):
        "creates beads and warnings where applicable"
        default: Dict[str, List] = {i: [] for i in ('type', 'message', 'bead', 'cycles')}
        tasks = self.cleaning.task, self.clipping.task
        ncy   = self.track.ncycles
        if any(i is not None for i in tasks):
            ctx = self.runcontext(GuiDataCleaningProcessor, GuiClippingProcessor)
            with ctx as view:
                if view is not None:
                    for _ in view:
                        pass

                for tsk in tasks:
                    if tsk is None:
                        pass

                    mem = ctx.taskcache(tsk).pop('messages', None)
                    # pylint: disable=unsupported-membership-test
                    mem = [i for i in mem if i[0] not in default['bead']]
                    if not mem:
                        pass

                    default['bead']    += [i[0] for i in mem]
                    default['cycles']  += [ncy if i[1] is None else i[1] for i in mem]
                    default['type']    += [i[2] for i in mem]
                    default['message'] += [i[3] for i in mem]
        self._ctrl.display.update(self.__display, messages = default)

    def badbeads(self) -> Set[BEADKEY]:
        "returns bead ids with messages"
        if self.track is None:
            return set()
        return set(self.messages()['bead']) # pylint: disable=unsubscriptable-object

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
        data = {'bad':       set(msg["bead"]), # pylint: disable=unsubscriptable-object
                'fixed':     set(i[-1] for i in self.availablefixedbeads),
                'ok':        set(self.track.beads.keys()),
                'missing':   set(self.__missing.filter(self.track.ncycles, msg)),
                'discarded': set(DataSelectionBeadController(self._ctrl).discarded)}

        for i, j in data.items():
            if i != "ok":
                data['ok'].difference_update(j)
                if i != "bad":
                    data['bad'].difference_update(j)
                    if i != "discarded":
                        j.difference_update(data['discarded'])
        return data

    def clear(self):
        "clears the model's cache"
        self._ctrl.display.update(self.__display, messages = {})

    def _ontask(self, parent = None, task = None, **_):
        if self.impacts(parent, task):
            self.clear()

class DriftControlPlotTheme(PlotTheme):
    "drift control plot theme"
    name             = "qc.driftcontrol.plot"
    measures         = PlotAttrs('', '-', 2, alpha     = .75)
    median           = PlotAttrs('', '-', 2, line_dash = 'dashed')
    pop10            = PlotAttrs('', '-', 2, line_dash = [4])
    pop90            = PlotAttrs('', '-', 2, line_dash = [4])
    colors           = dict(dark  = dict(measures = 'lightblue',
                                         median   = 'lightgreen',
                                         pop10    = 'lightgreen',
                                         pop90    = 'lightgreen'),
                            basic = dict(measures = 'darkblue',
                                         median   = 'darkgreen',
                                         pop10    = 'darkgreen',
                                         pop90    = 'darkgreen'))
    figsize          = PlotTheme.defaultfigsize(700, 150)
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
    def __init__(self):
        self.name             : str                     = "qc.driftcontrol"
        self.percentiles      : List[int]               = [10, 50, 90]
        self.yspan            : Tuple[List[int], float] = ([5, 95], 0.3)
        self.phases           : Tuple[int, int]         = (PHASE.initial, PHASE.pull)
        self.warningthreshold : float                   = 0.3

class DriftControlPlotModel(PlotModel):
    "qc plot model"
    theme   = DriftControlPlotTheme()
    config  = DriftControlPlotConfig()
    display = PlotDisplay(name = "qc")

    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        super().__init__()

class ExtensionPlotConfig(DriftControlPlotConfig):
    "allows configuring the drift control plots"
    def __init__(self):
        super().__init__()
        self.name             : str       = "qc.extension"
        self.ybarspercentiles : List[int] = [25, 75]
        self.warningthreshold : float     = 1.5e-2

class ExtensionPlotTheme(DriftControlPlotTheme):
    "drift control plot theme"
    name       = "qc.extension.plot"
    ylabel     = 'δ(Φ3-Φ1) (µm)'
    measures   = PlotAttrs('', 'o', 2, alpha = .75)
    ybars      = PlotAttrs('', 'vbar', 1,   alpha = .75)
    ymed       = PlotAttrs('', 'vbar', 1,   fill_alpha = 0.)
    colors     = dict(DriftControlPlotTheme.colors)
    colors['dark'] .update(ybars = 'lightblue', ymed = 'lightblue')
    colors['basic'].update(ybars = 'darkblue',  ymed = 'darkblue')
    ybarswidth = .8
    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        super().__init__(**_)
