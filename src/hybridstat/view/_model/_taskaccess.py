#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Model for peaksplot"
from   copy                     import deepcopy
from   typing                   import (
    Set, Optional, Dict, Tuple, Any, Sequence, ClassVar, Type,
    Iterator, cast
)

import numpy                    as     np

from peakfinding.histogram      import interpolator
from peakfinding.selector       import PeakSelectorDetails
from peakfinding.processor      import BaselinePeakProcessor, SingleStrandProcessor
from peakcalling                import match
from peakcalling.toreference    import ChiSquareHistogramFit
from peakcalling.tohairpin      import HairpinFitter, PeakMatching, Range
from peakcalling.processor.fittoreference   import FitData
from peakcalling.processor.fittohairpin     import Constraints, DistanceConstraint, FitBead
from taskcontrol.modelaccess    import TaskAccess
from taskmodel                  import RootTask, DataSelectionTask
from utils                      import updatecopy, NoArgs

from ...reporting.batch         import fittohairpintask
from ._processors               import runrefbead

# pylint: disable=unused-import,wrong-import-order,ungrouped-imports
from eventdetection.processor.__config__ import EventDetectionTask
from peakfinding.processor.__config__    import (PeakSelectorTask, SingleStrandTask,
                                                 BaselinePeakFilterTask)
from peakcalling.processor.__config__    import FitToHairpinTask, FitToReferenceTask

_DUMMY = type('_DummyDict', (),
              dict(get          = lambda *_: None,
                   __contains__ = lambda _: False,
                   __len__      = lambda _: 0,
                   __iter__     = lambda _: iter(())))()
ConstraintsDict = Dict[RootTask, Constraints]


class FitToReferenceConfig:
    """
    stuff needed to display the FitToReferenceTask
    """
    def __init__(self):
        self.name:          str   = 'hybridstat.fittoreference'
        self.histmin:       float = 1e-4
        self.peakprecision: float = 1e-2

class FitToReferenceStore:
    """
    stuff needed to display the FitToReferenceTask
    """
    DEFAULTS = dict(ident        = None,   reference = None,
                    fitdata      = _DUMMY, peaks     = _DUMMY,
                    interpolator = _DUMMY)

    def __init__(self, reference = None):
        self.name:         str                 = 'hybridstat.fittoreference'
        self.ident:        Optional[bytes]     = None
        self.reference:    Optional[RootTask]  = reference
        self.refcache:     Dict[RootTask, Any] = {}
        self.fitdata:      Dict[RootTask, Any] = {}
        self.peaks:        Dict[RootTask, Any] = {}
        self.interpolator: Dict[RootTask, Any] = {}

class FitToReferenceAccess(TaskAccess, tasktype = FitToReferenceTask):
    "access to the FitToReferenceTask"
    def __init__(self, mdl):
        super().__init__(mdl)
        self.__store = FitToReferenceStore()
        self.__theme = FitToReferenceConfig()

    @property
    def params(self) -> Optional[Tuple[float, float]]:
        "returns the computed stretch or 1."
        # pylint: disable=no-member
        return self.__store.refcache.get(self.bead, (1., 0.))

    refcache = property(lambda self: self.__store.refcache)
    fitalg   = property(lambda self: ChiSquareHistogramFit())
    stretch  = property(lambda self: self.params[0])
    bias     = property(lambda self: self.params[1])
    hmin     = property(lambda self: self.__theme.histmin)

    def update(self, **kwa):
        "removes the task"
        if not kwa.get("disabled", False):
            assert len(kwa) == 0
            if not self.__computefitdata():
                return
            kwa['fitdata'] = self.__store.fitdata
        super().update(**kwa)

    @property
    def reference(self) -> Optional[RootTask]:
        "returns the root task for the reference data"
        return self.__store.reference

    @reference.setter
    def reference(self, val):
        "sets the root task for the reference data"
        if val is not self.reference:
            info = FitToReferenceStore(reference = val).__dict__
            info.pop('name')
            self._updatedisplay(self.__store, **info)

    @property
    def referencepeaks(self) -> Optional[np.ndarray]:
        "returns reference peaks"
        # pylint: disable=no-member
        pks = self.__store.peaks.get(self.bead, None)
        return None if pks is None or len(pks) == 0 else pks

    def swapmodels(self, ctrl):
        "swap models for those in the controller"
        super().swapmodels(ctrl)
        self.__store = ctrl.display.swapmodels(self.__store)
        self.__theme = ctrl.theme.swapmodels(self.__theme)

    def observe(self, ctrl):
        "observes the global model"

        @ctrl.display.observe(self.__store)
        @ctrl.display.hashwith(self.__store)
        def _onref(old = None, **_):
            if 'reference' in old:
                self.resetmodel()

        @ctrl.tasks.observe("updatetask", "addtask", "removetask")
        @ctrl.display.hashwith(self.__store)
        def _ontask(parent = None, **_):
            if parent is self.reference:
                info = FitToReferenceStore(reference = self.reference).__dict__
                info.pop('name')
                ctrl.display.update(self.__store, **info)

        @ctrl.tasks.observe("closetrack")
        @ctrl.display.hashwith(self.__store)
        def _onclosetask(task, **_):
            if task is self.reference:
                info = FitToReferenceStore(reference = None).__dict__
                info.pop('name')
                ctrl.display.update(self.__store, **info)

    def resetmodel(self):
        "adds a bead to the task"
        if self.reference not in (self.roottask, None):
            return self.update()
        return self.update(disabled = True) if self.task else None

    def refhistogram(self, xaxis):
        "returns the histogram interpolated to the provided values"
        intp = self.__store.interpolator.get(self.bead, None)
        if self.reference == self.roottask:
            intp = None

        vals = np.full(len(xaxis), np.NaN, dtype = 'f4') if intp is None else intp(xaxis)
        if len(vals):
            # dealing with a visual bug: extremes should always be set to 0.
            vals[[0,-1]] = 0.
        return vals

    def identifiedpeaks(self, peaks, bead = NoArgs):
        "returns an array of identified peaks"
        if bead is NoArgs:
            bead = self.bead
        ref = self.__store.peaks.get(bead, None)
        arr = np.full(len(peaks), np.NaN, dtype = 'f4')
        if len(peaks) and ref is not None and len(ref):
            ids = match.compute(ref, peaks, self.__theme.peakprecision)
            arr[ids[:,1]] = ref[ids[:,0]]
        return arr

    @staticmethod
    def _configattributes(_):
        return {}

    def __computefitdata(self) -> bool:
        args  = {}  # type: Dict[str, Any]
        ident = self.statehash(self.reference, ...)
        if self.__store.ident == ident:
            if self.referencepeaks is not None:
                return False
        else:
            args.update(ident = ident, refcache = {})

        fits  = self.__store.fitdata
        if not fits:
            args['fitdata'] = fits = {}

        peaks  = self.__store.peaks
        if not peaks:
            args['peaks'] = peaks = {}

        intps  = self.__store.interpolator
        if not intps:
            args['interpolator'] = intps = {}

        ibead              = self.bead
        pks: Sequence[Any] = []
        try:
            if self.reference is not None and ibead is not None:
                pks, dtls = runrefbead(self._ctrl, self.reference, ibead)
        except Exception as exc:  # pylint: disable=broad-except
            self._updatedisplay("message", message = exc)

        peaks[ibead] = np.array([i for i, _ in pks], dtype = 'f4')
        if len(pks):
            fits[ibead]  = FitData(self.fitalg.frompeaks(pks), (1., 0.))  # type: ignore
            intps[ibead] = interpolator(dtls, miny = self.hmin, fill_value = 0.)

        if args:
            self._updatedisplay(self.__store, **args)
        return True

class FitToHairpinConfig:
    """
    stuff needed to display the FitToHairpinTask
    """
    def __init__(self):
        cls                                 = FitToHairpinTask
        self.name:        str               = 'hybridstat.fittohairpin'
        self.fit:         HairpinFitter     = cls.DEFAULT_FIT()
        self.match:       PeakMatching      = cls.DEFAULT_MATCH()
        self.constraints: Dict[str, Range]  = deepcopy(cls.DEFAULT_CONSTRAINTS)
        self.stretch:     Tuple[float, int] = (5.,   1)
        self.bias:        Tuple[float, int] = (5e-3, 1)

    def zscaled(self, value) -> Iterator[Tuple[str, Any]]:
        "rescale the config"
        yield ('fit',         self.fit.rescale(value))
        yield ('constraints', {i: j.rescale(i, value) for i, j in self.constraints.items()})
        yield ('stretch',     (self.stretch[0] / value, self.stretch[1]))
        yield ('bias',        (self.bias[0]   * value, self.bias[1]))

class FitToHairpinDisplay:
    """
    stuff needed to display the FitToHairpinTask
    """
    def __init__(self):
        self.name:        str             = 'hybridstat.fittohairpin'
        self.constraints: ConstraintsDict = {}

class FitToHairpinAccess(TaskAccess, tasktype = FitToHairpinTask):
    "access to the FitToHairpinTask"
    tasktype:   ClassVar[Type[FitToHairpinTask]]

    def __init__(self, mdl):
        super().__init__(mdl)
        self.__defaults        = FitToHairpinConfig()
        self.__factorydefaults = FitToHairpinConfig()
        self.__store           = FitToHairpinDisplay()

    def getforcedbeads(self, seq: Optional[str]) -> Set[int]:
        "return the bead forced to the current sequence key"
        if seq is not None:
            task = cast(FitToHairpinTask, self.task)
            if task is not None:
                return {i for i, j in task.constraints.items() if j.hairpin == seq}
        return set()

    def setforcedbeads(self, seq: Optional[str], values: Set[int]):
        "return the bead forced to the current sequence key"
        forced = self.getforcedbeads(seq)
        if forced == values:
            return

        if seq is None:
            return

        task = self.task
        if task is None:
            return
        root        = cast(RootTask, self.roottask)
        cstrs       = dict(self.__store.constraints)
        cstrs[root] = cur = dict(cstrs.get(root, {}))
        for i in forced-values:
            if cur[i].constraints:
                cur[i] = DistanceConstraint(None, cur[i].constraints)
            else:
                del cur[i]

        for i in values-forced:
            cur[i] = DistanceConstraint(seq, {})

        self._updatedisplay(self.__store, constraints = cstrs)
        self.update(constraints = deepcopy(cur))

    def newconstraint(self,
                      hairpin: Optional[str],
                      stretch: Optional[float],
                      bias:    Optional[float]):
        "update the constraints"
        if self.constraints() == (hairpin, stretch, bias):
            return

        root, bead  = cast(RootTask, self.roottask), cast(int, self.bead)
        cstrs       = dict(self.__store.constraints)
        cstrs[root] = dict(cstrs.get(root, {}))
        if (hairpin, stretch, bias) == (None, None, None):
            cstrs[root].pop(bead, None)
        else:
            params = {}
            if stretch is not None:
                params["stretch"] = Range(stretch, *self.__defaults.stretch)
            if bias is not None:
                params["bias"]    = Range(bias, *self.__defaults.bias)

            cstrs[root][bead] = DistanceConstraint(hairpin, params)

        self._updatedisplay(self.__store, constraints = cstrs)
        if  self.task is not None:
            self.update(constraints = deepcopy(cstrs[root]))

    def constraints(
            self,
            root: Optional[RootTask] = None,
            bead: Optional[int]      = None
    ) -> Tuple[Optional[str], Optional[float], Optional[float]]:
        "returns the constraints"
        root = self.roottask if root is None else root
        bead = self.bead     if bead is None else bead
        if root is None or bead is None:
            return None, None, None

        # pylint: disable=no-member
        cur = self.__store.constraints.get(root, {}).get(bead, None)
        if cur is None:
            return None, None, None

        return (cur[0],
                cur[1].get("stretch", (None,))[0],
                cur[1].get("bias",    (None,))[0])

    def update(self, **kwa):
        "removes the task"
        cache = self.cache()  # pylint: disable=not-callable
        if len(kwa) != 1 or 'constraints' not in kwa or not cache:
            super().update(**kwa)
        else:
            cur = self.task.constraints
            new = kwa['constraints']
            for i in set(cur) ^ set(new):
                cache.pop(i, None)
            for i in set(cur) & set(new):
                if cur[i] != new[i]:
                    cache.pop(i, None)

            super().update(**kwa)
            if cache:
                self.cache = cache

    def swapmodels(self, ctrl):
        "swap models for those in the controller"
        super().swapmodels(ctrl)
        self.__store           = ctrl.display.swapmodels(self.__store)
        self.__defaults        = ctrl.theme.swapmodels(self.__defaults)
        self.__factorydefaults = ctrl.theme.model(self.__defaults, defaults = True)

    def observe(self, ctrl):
        "observes the global model"
        keys = {'probes', 'path', 'constraintspath', 'useparams', 'fit', 'match'}

        @ctrl.theme.observe(self._tasksmodel.sequencemodel.config)
        @ctrl.display.observe(self._tasksmodel.peaksmodel.display)
        @ctrl.theme.observe(self.__defaults)
        @ctrl.display.hashwith(self._tasksdisplay)
        def _observe(old, **_):
            if keys.intersection(old):
                task = self.default(self._tasksmodel)
                self.update(**(task.config() if task else {'disabled': True}))

        @ctrl.tasks.observe("addtask", "updatetask", "removetask")
        @ctrl.display.hashwith(self._tasksdisplay)
        def _ondataselection(task, cache, **_):
            if isinstance(task, DataSelectionTask):
                for proc, elem in cache:
                    if isinstance(proc.task, self.tasktype) and elem:
                        for i in task.discarded:
                            elem.pop(i, None)
                        self.cache = elem

        @ctrl.display.observe
        @ctrl.display.hashwith(self.__store)
        def _onopenanafile(model, **_):
            tasklist = model.get('tasks', [[None]])[0]
            task     = next((i for i in tasklist if isinstance(i, FitToHairpinTask)),
                            None)
            if task is not None:
                root  = tasklist[0]
                cstrs = dict(task.constraints)

                def _fcn(model = None,  **_):
                    if model[0] is not root:
                        return
                    cur       = dict(self.__store.constraints)
                    cur[root] = cstrs
                    ctrl.display.update(self.__store, constraints = cur)
                ctrl.tasks.oneshot("opentrack", _fcn)

    @staticmethod
    def _configattributes(kwa):
        return {}

    def updatedefault(self, attr, inst = None, **kwa):
        "updates the identifiers for this task"
        if inst is None and len(kwa) == 0:
            return

        inst = (inst() if isinstance(inst, type) else
                inst   if inst is not None       else
                getattr(self.__defaults, attr))
        self._updatetheme(self.__defaults, **{attr: updatecopy(inst, **kwa)})

    def defaultattribute(self, name, usr):
        "return a task attribute"
        return getattr(self.__defaults if usr else self.__factorydefaults, name)

    def attribute(self, name, key = NoArgs):
        "return a task attribute"
        task = self.task
        if task is None:
            return getattr(self.__defaults, name)
        attr = getattr(task, name)
        return attr if key is NoArgs else attr[key]

    def default(self, mdl):
        "returns the default identification task"
        ols = mdl.oligos
        if ols is None or len(ols) == 0 or len(mdl.sequences(...)) == 0:
            return None

        dist = self.__defaults.fit
        pid  = self.__defaults.match
        cstr = self.__defaults.constraints
        try:
            task = fittohairpintask(mdl.sequencepath,    ols,
                                    mdl.constraintspath, mdl.useparams,
                                    constraints = cstr, fit = dist, match = pid)
        except FileNotFoundError:
            return None
        task.constraints.update(self.__store.constraints.get(self.roottask, {}))
        return task

    def rescale(self, ctrl, mdl, value):
        "rescale the model"
        ctrl.theme.update(self.__defaults, **dict(self.__defaults.zscaled(value)))
        self.resetmodel(mdl)

    def resetmodel(self, mdl):
        "resets the model"
        task = self.default(mdl)
        cur  = self.task
        if task is None and cur is not None:
            self.update(disabled = True)
        elif task != cur:
            self.update(**task.config())

class EventDetectionTaskAccess(TaskAccess, tasktype = EventDetectionTask):
    "access to the EventDetectionTask"

class PeakSelectorTaskAccess(TaskAccess, tasktype = PeakSelectorTask):
    "access to the PeakSelectorTask"

class SingleStrandConfig:
    "Whether the task is automatically added & removed according to oligos"
    def __init__(self):
        self.automated = True
        self.name      = "singlestrand"

class SingleStrandTaskAccess(TaskAccess, tasktype = SingleStrandTask):
    "access to the SingleStrandTask"
    def __init__(self, mdl):
        super().__init__(mdl)
        self.__config = SingleStrandConfig()

    def swapmodels(self, ctrl):
        "swap models for those in the controller"
        super().swapmodels(ctrl)
        self.__config = ctrl.theme.swapmodels(self.__config)

    def observe(self, ctrl):
        "observes the global model"

        @ctrl.theme.observe(self.__config)
        @ctrl.theme.hashwith(self._tasksdisplay)
        def _ontasks(**_):
            self._tasksmodel.reset()

    def resetmodel(self, mdl):
        "resets the model"
        self.update(disabled = not (self.__config.automated and mdl.hassinglestrand))

    def compute(
            self,
            fitdata: Optional[FitBead],
            dtl: Optional[PeakSelectorDetails]
    ) -> Optional[float]:
        "return the index of the baseline if it exists"
        if dtl is None or len(dtl) == 0:
            return None
        if fitdata:
            return fitdata.singlestrand
        proc   = SingleStrandProcessor(self.task if self.task else self.defaultconfigtask)
        dframe = next(iter(self.processors(PeakSelectorTask).run(copy = True)))
        out    = proc.index(dframe, self.bead, dtl)
        return None if out is None or out >= len(dtl) else dtl[out][0]

class BaselinePeakFilterTaskAccess(TaskAccess, tasktype = BaselinePeakFilterTask):
    "access to the BaselinePeakFilterTask"
    def compute(
            self,
            fitdata: Optional[FitBead],
            dtl: Optional[PeakSelectorDetails]
    ) -> Optional[float]:
        "return the index of the single strand peak if it exists"
        if dtl is None or len(dtl) == 0:
            return None
        if fitdata:
            return fitdata.baseline
        proc   = BaselinePeakProcessor(self.task if self.task else self.defaultconfigtask)
        dframe = next(iter(self.processors(PeakSelectorTask).run(copy = True)))
        out    = proc.index(dframe, self.bead, dtl)
        return None if out is None else dtl[out][0]
