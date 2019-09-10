#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"access to the model"
from typing                         import Optional, List, Dict, Tuple, Any, cast
import numpy as np

# pylint: disable=unused-import
from control.decentralized               import Indirection
from eventdetection.processor.__config__ import ExtremumAlignmentTask
from model.plots                         import PlotAttrs, PlotTheme, PlotModel, PlotDisplay
from taskcontrol.modelaccess             import TaskPlotModelAccess, TaskAccess
from taskmodel                           import RootTask
from taskmodel.application               import rescalingevent
from utils                               import NoArgs, initdefaults
from ..beadsubtraction                   import FixedBeadDetection, FixedList
from ..processor.__config__              import (
    DataCleaningTask, BeadSubtractionTask, ClippingTask, UndersamplingTask
)

class UndersamplingTaskAccess(TaskAccess, tasktype = UndersamplingTask):
    "access to undersampling task"

class DataCleaningAccess(TaskAccess, tasktype = DataCleaningTask):
    "access to data cleaning"
    @property
    def cache(self):
        "returns the object cache"
        mem = super().cache()
        if mem is None:
            return None

        cur = mem.get(self.bead, None)
        return None if cur is None else {i.name: i for i in cur[0]}

    @cache.setter
    def cache(self, value):
        "set the cache object"
        raise NotImplementedError()

    def saturatedcycles(self, cache):
        "returns saturated cycles"
        sat                = cache['saturation'].values
        sat[np.isnan(sat)] = 0.
        return np.nonzero(sat > self.task.maxdisttozero)

    def nbadcycles(self, cache = NoArgs) -> int:
        "returns the number of bad cycles"
        return len(self.badcycles(cache))

    def sorted(self, order, cache = NoArgs):
        "returns cycles ordered by category"
        astats = self.cache if cache is NoArgs else cache
        if astats is None:
            return (np.zeros(1, dtype = 'i4') if self.track is None     else
                    np.arange(self.track.ncycles, dtype = 'i4'))

        stats = astats if isinstance(astats, dict) else dict(astats)
        if 'discarded' in stats:
            cpy = np.copy(stats['discarded'].values)
            nan = np.isnan(cpy)
            cpy[~nan] *= -1
            cpy[nan]   = np.nonzero(nan)[0]+1
            return np.argsort(cpy)

        res   = np.full(len(next(iter(stats.values())).values), -1, dtype = 'i4')
        for i, name in enumerate(order):
            stat = stats.get(name, None)
            if stat is not None:
                cur      = np.union1d(stat.min, stat.max)
                res[cur] = cur+i*len(res)

        cur      = np.arange(len(res), dtype = 'i4')[res == -1]
        res[cur] = cur+order.index('good')*len(res)
        return np.argsort(res)

    def badcycles(self, cache = NoArgs):
        "returns bad cycles"
        return DataCleaningTask.badcycles(self.cache if cache is NoArgs else cache)

class BeadSubtractionAccess(TaskAccess, tasktype = BeadSubtractionTask):
    "access to bead subtraction"
    @property
    def beads(self):
        "returns beads to subtract"
        return getattr(self.task, 'beads', [])

    @beads.setter
    def beads(self, vals):
        "returns beads to subtract"
        lst               = list(vals) if vals else []
        self.update(beads = sorted(lst), disabled = len(lst) == 0)

    def referencebeads(self) -> Optional[List[int]]:
        "return beads from the reference if they exist"
        track = self.track
        root  = self._ctrl.theme.get("fittoreference", "reference", None)
        if root is None or track is None:
            return None

        lst  = self._ctrl.tasks.tasklist(root)
        task = next((t for t in lst if isinstance(t, self.tasktype)), None)
        if task is None:
            return []

        mine  = set(track.beads.keys())
        beads = [i for i in cast(BeadSubtractionTask, task).beads if i in mine]
        return beads

    def switch(self, bead):
        "adds or removes the bead"
        self.beads = set(self.beads).symmetric_difference({bead})

    @staticmethod
    def _configattributes(kwa):
        return {}

class ExtremumAlignmentTaskAccess(TaskAccess, tasktype = ExtremumAlignmentTask):
    "access to bead subtraction"

class ClippingTaskAccess(TaskAccess, tasktype = ClippingTask):
    "access to the ClippingTask"

class FixedBeadDetectionConfig(FixedBeadDetection):
    """
    Fixed bead detection configuration.

    Warning: the class name must end with Config in order for the config file to be
    good.
    """
    name:      str   = "fixedbeads"
    rescaling: float = 1.
    automate:  bool  = True

    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        super().__init__(**_)

class FixedBeadDetectionStore:
    "For saving in the right place"
    name                             = "fixedbeads"
    data: Dict[RootTask, FixedList] = {}
    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        pass

class DataCleaningModelAccess(TaskPlotModelAccess):  # pylint: disable=too-many-instance-attributes
    "Access to cleaning tasks"
    _fixedbeadsconfig = Indirection()
    _fixedbeadsstore  = Indirection()
    __ADDED           = False   # TODO: Make modelacces MVC and remove this classvar

    def __init__(self, ctrl, **_):
        super().__init__(ctrl)
        self.undersampling     = UndersamplingTaskAccess(self)
        self._fixedbeadsconfig = FixedBeadDetectionConfig()
        self._fixedbeadsstore  = FixedBeadDetectionStore()
        self.alignment         = ExtremumAlignmentTaskAccess(self)
        self.clipping          = ClippingTaskAccess(self)
        self.cleaning          = DataCleaningAccess(self)
        self.subtracted        = BeadSubtractionAccess(self)

    def addto(self, ctrl, noerase = False):
        "add to the controller"
        if self.__ADDED:
            return
        self.__class__.__ADDED = True  # pylint: disable=protected-access

        @ctrl.tasks.observe
        def _onclosetrack(task = None, **_):
            data = self._fixedbeadsstore.data
            if task in data:
                info = dict(data)
                info.pop(task, None)
                self._fixedbeadsstore = {'data': info}

        @ctrl.tasks.observe
        def _onopentrack(calllater = None, isarchive = False, **_):
            if not self._fixedbeadsconfig.automate or isarchive:
                return

            @calllater.append
            def _addsubtracted(*_1, **_2):
                beads = self.availablefixedbeads
                self.subtracted.update(beads = [i[-1] for i in beads])

        @ctrl.theme.observe
        @ctrl.display.observe
        def _ontasks(old = None, **_):
            done, cur, coeff = rescalingevent(ctrl, old, self._fixedbeadsconfig.rescaling)
            if not done:
                ctrl.theme.update(
                    self._fixedbeadsconfig,
                    rescaling = cur,
                    **dict(self._fixedbeadsconfig.zscaled(coeff))
                )

        @ctrl.theme.observe(self._fixedbeadsconfig)
        def _onchangeconfig(**_):
            self._fixedbeadsstore = {'data': {}}

    @property
    def availablefixedbeads(self) -> FixedList:
        "returns bead ids for potential fixed beads"
        root = self.roottask
        if root is None:
            return []

        data  = self._fixedbeadsstore.data
        beads = data.get(root, None)
        if beads is None:
            track = self._ctrl.tasks.track(root)
            if track is None:
                return []

            info  = dict(data)
            beads = info[root] = self._fixedbeadsconfig(track.beads)
            self._fixedbeadsstore = {'data': info}
        return beads

class CleaningPlotTheme(PlotTheme):
    """
    cleaning plot theme
    """
    name:          str                  = "cleaning.theme"
    lines:         PlotAttrs            = PlotAttrs('~gray', '-', 1, alpha                = .3)
    points:        PlotAttrs            = PlotAttrs('color', 'o', 1, alpha                = .5)
    hover:         PlotAttrs            = PlotAttrs('white', 'o', 4, alpha                = 0.)
    figsize:       Tuple[int, int, str] = PlotTheme.defaultfigsize(300, 500)
    clip:          int                  = 3
    clipovershoot: float                = 10
    maxfixedbeads: int                  = 15
    widgetwidth:   int                  = 535
    ntitles:       int                  = 5
    order:         Tuple[str,...]       = (
        'aberrant', 'hfsigma', 'extent', 'population',
        'pingpong', 'alignment', 'clipping', 'saturation', 'good'
    )
    colors:        Dict[str, str]       = dict(
        good       = '#6baed6',  # blue
        hfsigma    = 'gold',
        extent     = 'orange',
        population = 'hotpink',
        pingpong   = 'firebrick',
        saturation = 'chocolate',
        alignment  = 'darkgray',
        clipping   = 'darkorchid',
        aberrant   = 'red'
    )
    tooltips: List[Tuple[str, ...]] = [
        ('(cycle, t, z, status)', '(@cycle, $~x{1}, $data_y{1.1111}, @status)')
    ]
    toolbar:  Dict[str, Any]        = dict(
        PlotTheme.toolbar,
        items = 'pan,box_zoom,ypan,ybox_zoom,ywheel_zoom,reset,save,dpxhover'
    )
    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        super().__init__(**_)

class CleaningPlotModel(PlotModel):
    """
    cleaning plot model
    """
    theme   = CleaningPlotTheme()
    display = PlotDisplay(name = "cleaning")
