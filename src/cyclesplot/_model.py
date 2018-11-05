#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"access to the model"

from typing                   import Optional, Dict, cast
from utils                    import NoArgs, initdefaults
from model.task               import RootTask
from model.task.application   import TasksDisplay
from model.plots              import PlotTheme, PlotModel, PlotAttrs, PlotDisplay
from control.modelaccess      import TaskAccess
from sequences.modelaccess    import SequencePlotModelAccess

# pylint: disable=unused-import
from cordrift.processor       import DriftTask
from cleaning.processor       import ClippingTask
from eventdetection.processor import EventDetectionTask, ExtremumAlignmentTask

class CyclesModelConfig:
    """
    added info for cycles
    """
    name             = "cycles"
    showevents       = False
    binwidth         = 0.01
    minframes        = 10
    estimatedstretch = 1./8.8e-4

    @initdefaults(frozenset(locals()))
    def __init__(self, **kwa):
        pass

class CyclesPlotTheme(PlotTheme):
    "theme for cycles"
    name       = "cycles.plot"
    raw        = {'dark':  PlotAttrs('color', 'circle', .1, alpha = .5,
                                     palette = 'YlOrBr'),
                  'basic': PlotAttrs('color', 'circle', .1, alpha = .5,
                                     palette = 'inferno')}
    selection  = {'dark'  : PlotAttrs('lightblue', 'line',   3),
                  'basic' : PlotAttrs('blue', 'line',   3)}
    tooltips   = [('(cycle, t, z)', '(@cycle, $~x{1}, $data_y{1.1111})')]
    radius     = 1.
    histframes     = PlotAttrs({'dark': 'darkgray', 'basic': 'gray'},
                               'quad', 1, fill_color = 'gray')
    histcycles     = PlotAttrs({"dark": 'darkcyan', "basic": "blue"},
                               'quad', 1, fill_color = None, line_alpha = .5)
    histxtoplabel  = 'Cycles'
    histxlabel     = 'Frames'
    figsize        = 450, 450, 'fixed'
    toolbar        = dict(PlotTheme.toolbar)
    toolbar.update(raw   = 'tap,ypan,ybox_zoom,reset,save,dpxhover',
                   items = 'ypan,ybox_zoom,reset,save,dpxhover')
    @initdefaults(frozenset(locals()))
    def __init__(self, **kwa):
        super().__init__(**kwa)

class BeadInfo:
    """
    bead related info
    """
    stretch: float           = CyclesModelConfig.estimatedstretch
    bias   : Optional[float] = None
    @initdefaults
    def __init__(self, **kwa):
        pass

INFO = Dict[RootTask, Dict[int, BeadInfo]]
class CyclesPlotDisplay(PlotDisplay):
    "CyclesPlotDisplay"
    name             = "cycles"
    info: INFO       = {}
    estimatedstretch = CyclesModelConfig.estimatedstretch
    estimatedbias    = 0.
    @initdefaults
    def __init__(self, **kwa):
        super().__init__(**kwa)

    def __getitem__(self, tasks: TasksDisplay) -> Optional[BeadInfo]:
        root, bead = tasks.roottask, tasks.bead
        if root is None or bead is None:
            return None
        return self.info.get(root, {}).get(bead, None)

    def newinfo(self, tasks: TasksDisplay, **info) -> Optional[INFO]:
        "return a dict containing the new info"
        root, bead = tasks.roottask, tasks.bead
        if root is None or bead is None:
            return None
        old = self.info.get(root, {}).get(bead, None)
        if old and all(getattr(old, i) == j for i, j in info.items()):
            return None

        if old is None:
            info.setdefault('stretch', self.estimatedstretch)
            info.setdefault('bias',    self.estimatedbias)
            old = BeadInfo(**info)
        else:
            old.__dict__.update(**info)

        res: INFO = dict(self.info)
        res.setdefault(root, {})[bead] = cast(BeadInfo, old)
        return res

class CyclesPlotModel(PlotModel):
    "model for cycles"
    theme   = CyclesPlotTheme()
    display = CyclesPlotDisplay()
    config  = CyclesModelConfig()

class EventDetectionTaskAccess(TaskAccess, tasktype = EventDetectionTask):
    "Access to the event detection task"
    def __init__(self, mdl):
        super().__init__(mdl)
        self.__model = self._ctrl.theme.model(CyclesModelConfig())

    @property
    def task(self) -> Optional[EventDetectionTask]:
        "returns the task if it exists"
        if not self.__model.showevents:
            return None
        return cast(EventDetectionTask, super().task)

    def check(self, task, parent = NoArgs) -> bool:
        "wether this controller deals with this task"
        return self.__model.showevents and super().check(task, parent)

    def update(self, **kwa):
        "adds/updates the task"
        self._ctrl.theme.update(self.__model, showevents = not kwa.pop('disabled', False))
        super().update(**kwa)

class ExtremumAlignmentTaskAccess(TaskAccess, tasktype = ExtremumAlignmentTask):
    "access to ExtremumAlignmentTask"

class ClippingTaskAccess(TaskAccess, tasktype = ClippingTask, disabled = True):
    "access to the ClippingTask"

class BeadsDriftTaskAccess(TaskAccess,
                           tasktype   = DriftTask,
                           configname = 'driftperbead',
                           attrs      = {'onbeads': True}):
    "access to beads drift task"

class CyclesDriftTaskAccess(TaskAccess,
                            tasktype   = DriftTask,
                            configname = 'driftpercycle',
                            attrs      = {'onbeads': False}):
    "access to beads drift task"

class CyclesModelAccess(SequencePlotModelAccess):
    "Model for Cycles View"
    def __init__(self, ctrl) -> None:
        super().__init__(ctrl)
        self.cycles         = CyclesPlotModel.create(ctrl)
        self.alignment      = ExtremumAlignmentTaskAccess(self)
        self.clipping       = ClippingTaskAccess(self)
        self.driftperbead   = BeadsDriftTaskAccess(self)
        self.driftpercycle  = CyclesDriftTaskAccess(self)
        self.eventdetection = EventDetectionTaskAccess(self)

    @property
    def stretch(self) -> None:
        "return the stretch for the current bead"
        out = self.cycles.display[self.sequencemodel.tasks]
        return out.stretch if out else self.cycles.display.estimatedstretch

    @property
    def bias(self) -> None:
        "return the bias for the current bead"
        out = self.cycles.display[self.sequencemodel.tasks]
        return out.bias if out else self.cycles.display.estimatedbias

    def newparams(self, **info):
        "set stretch and bias"
        self.cycles.display.newinfo(self.sequencemodel.tasks, **info)

    def runbead(self):
        "returns a tuple (dataitem, bead) to be displayed"
        cycs = super().runbead()
        if cycs is None:
            track = self.track
            return None if track is None else track.cycles[self.bead, ...]
        return cycs[self.bead,...]
