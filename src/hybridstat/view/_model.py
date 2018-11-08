#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Model for peaksplot"
import atexit
from   asyncio                  import wrap_future, sleep as _sleep
from   copy                     import copy
from   concurrent.futures       import ProcessPoolExecutor
from   typing                   import Optional, Dict, Tuple, Any, Sequence, cast
import pickle

import numpy                    as     np

from control.modelaccess        import TaskAccess
from cleaning.view              import (BeadSubtractionAccess,
                                        FixedBeadDetectionModel,
                                        FIXED_LIST)
from model.task                 import RootTask
from model.plots                import PlotModel, PlotTheme, PlotAttrs, PlotDisplay
from peakfinding.histogram      import interpolator
from peakfinding.selector       import PeakSelectorDetails
from peakcalling                import match
from peakcalling.toreference    import ChiSquareHistogramFit
from peakcalling.tohairpin      import Distance
from peakcalling.processor.fittoreference   import FitData
from peakcalling.processor.fittohairpin     import (Constraints, HairpinFitter,
                                                    PeakMatching, Range,
                                                    DistanceConstraint)
from sequences.modelaccess      import SequencePlotModelAccess
from utils                      import dataclass, dflt, updatecopy, initdefaults
from view.base                  import spawn

from ..reporting.batch          import fittohairpintask
from ._processors               import runbead, runrefbead
from ._peakinfo                 import createpeaks

# pylint: disable=unused-import,wrong-import-order,ungrouped-imports
from cleaning.processor.__config__       import ClippingTask
from eventdetection.processor.__config__ import EventDetectionTask, ExtremumAlignmentTask
from peakfinding.processor.__config__    import PeakSelectorTask, SingleStrandTask
from peakcalling.processor.__config__    import FitToHairpinTask, FitToReferenceTask

class PeaksPlotTheme(PlotTheme):
    """
    cleaning plot theme
    """
    name            = "hybridstat.peaks.plot"
    figsize         = 500, 700, "fixed"
    xtoplabel       = 'Duration (s)'
    xlabel          = 'Rate (%)'
    widgetsborder   = 10
    ntitles         = 4
    count           = PlotAttrs('lightblue', 'line', 1)
    eventscount     = PlotAttrs('lightblue', 'circle', 3)
    referencecount  = PlotAttrs('bisque', 'patch', alpha = 0.5)
    peaksduration   = PlotAttrs('lightgreen', 'diamond', 15, fill_alpha = 0.5,
                                angle = np.pi/2.)
    peakscount      = PlotAttrs('lightblue', 'triangle', 15, fill_alpha = 0.5,
                                angle = np.pi/2.)
    colors          = dict(dark  = dict(reference       = 'bisque',
                                        missing         = 'red',
                                        found           = 'black',
                                        count           = 'lightblue',
                                        eventscount     = 'lightblue',
                                        referencecount  = 'bisque',
                                        peaksduration   = 'lightgreen',
                                        peakscount      = 'lightblue'),
                           basic = dict(reference       = 'bisque',
                                        missing         = 'red',
                                        found           = 'gray',
                                        count           = 'darkblue',
                                        eventscount     = 'darkblue',
                                        referencecount  = 'bisque',
                                        peaksduration   = 'darkgreen',
                                        peakscount      = 'darkblue'))
    toolbar          = dict(PlotTheme.toolbar)
    toolbar['items'] = 'ypan,ybox_zoom,reset,save,dpxhover,tap'
    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        super().__init__(**_)

@dataclass
class PeaksPlotConfig:
    "PeaksPlotConfig"
    name:             str   = "hybridstat.peaks"
    estimatedstretch: float = 1./8.8e-4

class PeaksPlotDisplay(PlotDisplay):
    "PeaksPlotDisplay"
    name                              = "hybridstat.peaks"
    distances : Dict[str, Distance]   = dict()
    peaks:      Dict[str, np.ndarray] = dict()
    nprocessors                       = 0
    waittime                          = .1
    estimatedbias                     = 0.
    constraintspath: Any              = None
    useparams: bool                   = False
    @initdefaults(frozenset(locals()))
    def __init__(self, **kwa):
        super().__init__(**kwa)

class PeaksPlotModel(PlotModel):
    """
    cleaning plot model
    """
    theme   = PeaksPlotTheme()
    display = PeaksPlotDisplay()
    config  = PeaksPlotConfig()
    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        super().__init__()

@dataclass
class FitToReferenceConfig:
    """
    stuff needed to display the FitToReferenceTask
    """
    name          : str   = 'hybridstat.fittoreference'
    histmin       : float = 1e-4
    peakprecision : float = 1e-2

_DUMMY = type('_DummyDict', (),
              dict(get          = lambda *_: None,
                   __contains__ = lambda _: False,
                   __len__      = lambda _: 0,
                   __iter__     = lambda _: iter(())))()
@dataclass
class FitToReferenceStore:
    """
    stuff needed to display the FitToReferenceTask
    """
    DEFAULTS = dict(ident        = None,   reference = None,
                    fitdata      = _DUMMY, peaks     = _DUMMY,
                    interpolator = _DUMMY)
    name         : str = 'hybridstat.fittoreference'
    ident        : Any = dflt(None)
    reference    : Any = dflt(None)
    fitdata      : Any = dflt(_DUMMY)
    peaks        : Any = dflt(_DUMMY)
    interpolator : Any = dflt(_DUMMY)

class FitToReferenceAccess(TaskAccess, tasktype = FitToReferenceTask):
    "access to the FitToReferenceTask"
    def __init__(self, mdl):
        super().__init__(mdl)
        self.__store = FitToReferenceStore()
        self.__theme = FitToReferenceConfig()

    def addto(self, ctrl, noerase): # pylint: disable=arguments-differ
        "add to the controller"
        self.__store = ctrl.display.add(self.__store, noerase)
        self.__theme = ctrl.theme.add(self.__theme, noerase)

    @property
    def params(self) -> Optional[Tuple[float, float]]:
        "returns the computed stretch or 1."
        tsk = cast(FitToReferenceTask, self.task)
        if tsk is None or self.bead not in tsk.fitdata:
            return 1., 0.

        mem = self.cache() # pylint: disable=not-callable
        return (1., 0.) if mem is None else mem.get(self.bead, (1., 0.))

    fitalg  = property(lambda self: ChiSquareHistogramFit())
    stretch = property(lambda self: self.params[0])
    bias    = property(lambda self: self.params[1])
    hmin    = property(lambda self: self.__theme.histmin)

    def update(self, **kwa):
        "removes the task"
        if kwa.get("disabled", False):
            super().update(**kwa)
            return

        assert len(kwa) == 0
        newdata, newid = self.__computefitdata()
        if not newdata:
            return

        # pylint: disable=not-callable
        cache = None if newid else self.cache()
        super().update(fitdata = self.__store.fitdata)
        if cache:
            self._ctrl.tasks.processors(self.roottask).data.setCacheDefault(self.task, cache)

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
            self._ctrl.display.update(self.__store, **info)

    @property
    def referencepeaks(self) -> Optional[np.ndarray]:
        "returns reference peaks"
        pks = self.__store.peaks.get(self.bead, None)
        return None if pks is None or len(pks) == 0 else pks

    def setobservers(self, ctrl):
        "observes the global model"
        def _onref(old = None, **_):
            if 'reference' in old:
                self.resetmodel()
        ctrl.display.observe(self.__store, _onref)

        def _ontask(parent = None, **_):
            if parent == self.reference:
                info = FitToReferenceStore(reference = self.reference).__dict__
                info.pop('name')
                ctrl.display.update(self.__store, **info)
                self.resetmodel()
        ctrl.tasks.observe("updatetask", "addtask", "removetask", _ontask)

    def resetmodel(self):
        "adds a bead to the task"
        return (self.update()                if self.reference not in (self.roottask, None) else
                self.update(disabled = True) if self.task                                   else
                None)

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

    def identifiedpeaks(self, peaks):
        "returns an array of identified peaks"
        ref = self.referencepeaks
        arr = np.full(len(peaks), np.NaN, dtype = 'f4')
        if len(peaks) and ref is not None and len(ref):
            ids = match.compute(ref, peaks, self.__theme.peakprecision)
            arr[ids[:,1]] = ref[ids[:,0]]
        return arr

    @staticmethod
    def _configattributes(_):
        return {}

    def __computefitdata(self) -> Tuple[bool, bool]:
        args  = {} # type: Dict[str, Any]
        ident = pickle.dumps(tuple(self._ctrl.tasks.tasklist(self.reference)))
        if self.__store.ident == ident:
            if self.referencepeaks is not None:
                return False, False
        else:
            args['ident'] = ident

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
        except Exception as exc: # pylint: disable=broad-except
            self._ctrl.display.update("message", message = exc)

        peaks[ibead] = np.array([i for i, _ in pks], dtype = 'f4')
        if len(pks):
            fits [ibead] = FitData(self.fitalg.frompeaks(pks), (1., 0.)) # type: ignore
            intps[ibead] = interpolator(dtls, miny = self.hmin, fill_value = 0.)

        if args:
            self._ctrl.display.update(self.__store, **args)
        return True, 'ident' in args

@dataclass
class FitToHairpinConfig:
    """
    stuff needed to display the FitToHairpinTask
    """
    name        : str               = 'hybridstat.fittohairpin'
    fit         : HairpinFitter     = dflt(FitToHairpinTask.DEFAULT_FIT())
    match       : PeakMatching      = dflt(FitToHairpinTask.DEFAULT_MATCH())
    constraints : Dict[str, Range]  = dflt(FitToHairpinTask.DEFAULT_CONSTRAINTS)
    stretch     : Tuple[float, int] = (5.,   1)
    bias        : Tuple[float, int] = (5e-3, 1)

ConstraintsDict = Dict[RootTask, Constraints]
@dataclass
class FitToHairpinDisplay:
    """
    stuff needed to display the FitToHairpinTask
    """
    name:        str             = 'hybridstat.fittohairpin'
    constraints: ConstraintsDict = dflt({})

class FitToHairpinAccess(TaskAccess, tasktype = FitToHairpinTask):
    "access to the FitToHairpinTask"
    def __init__(self, mdl):
        super().__init__(mdl)
        self.__defaults = FitToHairpinConfig()
        self.__display  = FitToHairpinDisplay()

    def addto(self, ctrl, noerase): # pylint: disable=arguments-differ
        "add to the controller"
        self.__defaults = ctrl.theme.add(self.__defaults, noerase)
        self.__display  = ctrl.display.add(self.__display,  noerase)

    def newconstraint(self,
                      hairpin : Optional[str],
                      stretch : Optional[float],
                      bias    : Optional[float]):
        "update the constraints"
        if self.constraints() == (hairpin, stretch, bias):
            return

        root, bead  = cast(RootTask, self.roottask), cast(int, self.bead)
        cstrs       = dict(self.__display.constraints)
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

        self._ctrl.display.update(self.__defaults, constraints = cstrs)
        if  self.task is not None:
            self.update(constraints = {i: dict(j) for i, j in cstrs.items()})

    def constraints(self) -> Tuple[Optional[str], Optional[float], Optional[float]]:
        "returns the constraints"
        root, bead = self.roottask, self.bead
        if root is None or bead is None:
            return None, None, None

        cur = self.__display.constraints.get(root, {}).get(bead, None)
        if cur is None:
            return None, None, None

        return (cur[0],
                cur[1].get("stretch", (None,))[0],
                cur[1].get("bias",    (None,))[0])

    def setobservers(self, mdl, ctrl):
        "observes the global model"
        keys = {'probes', 'path', 'constraintspath', 'useparams', 'fit', 'match'}
        def _observe(old = None, **_):
            if keys.intersection(old):
                task = self.default(mdl)
                self.update(**(task.config() if task else {'disabled': True}))

        ctrl.theme  .observe(mdl.sequencemodel.config, _observe)
        ctrl.theme  .observe(self.__defaults,          _observe)
        ctrl.display.observe(mdl.peaksmodel.display,   _observe)

        @ctrl.display.observe
        def _onopenanafile(model = None, **_):
            tasklist = model.get('tasks', [[None]])[0]
            task     = next((i for i in tasklist if isinstance(i, FitToHairpinTask)),
                            None)
            if task is not None:
                root  = tasklist[0]
                cstrs = dict(task.constraints)
                def _fcn(model = None,  **_):
                    if model[0] is not root:
                        return
                    cur       = dict(self.__display.constraints)
                    cur[root] = cstrs
                    ctrl.display.update(self.__display, constraints = cur)
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
        self._ctrl.theme.update(self.__defaults, **{attr: updatecopy(inst, **kwa)})

    def defaultattribute(self, name, usr):
        "return a task attribute"
        return self._ctrl.theme.get(self.__defaults, name, defaultmodel = not usr)

    def default(self, mdl):
        "returns the default identification task"
        ols = mdl.oligos
        if ols is None or len(ols) == 0 or len(mdl.sequences(...)) == 0:
            return None

        dist = self.__defaults.fit
        pid  = self.__defaults.match
        cstr = self.__defaults.constraints
        task = fittohairpintask(mdl.sequencepath,    ols,
                                mdl.constraintspath, mdl.useparams,
                                constraints = cstr, fit = dist, match = pid)
        task.constraints.update(self.__display.constraints.get(self.roottask, {}))
        return task

    def resetmodel(self, mdl):
        "resets the model"
        task = self.default(mdl)
        cur  = self.task
        if task is None and cur is not None:
            self.update(disabled = True)
        elif task != cur:
            self.update(**task.config())

class ExtremumAlignmentTaskAccess(TaskAccess, tasktype = ExtremumAlignmentTask):
    "access to the ExtremumAlignmentTask"

class ClippingTaskAccess(TaskAccess, tasktype = ClippingTask):
    "access to the ClippingTask"

class EventDetectionTaskAccess(TaskAccess, tasktype = EventDetectionTask):
    "access to the EventDetectionTask"

class PeakSelectorTaskAccess(TaskAccess, tasktype = PeakSelectorTask):
    "access to the PeakSelectorTask"

class SingleStrandTaskAccess(TaskAccess, tasktype = SingleStrandTask):
    "access to the SingleStrandTask"

# pylint: disable=too-many-instance-attributes
class PeaksPlotModelAccess(SequencePlotModelAccess):
    "Access to peaks"
    def __init__(self, ctrl, addto = False):
        super().__init__(ctrl)
        self.peaksmodel      = PeaksPlotModel.create(ctrl, False)
        self.subtracted      = BeadSubtractionAccess(self)
        self.fixedbeads      = FixedBeadDetectionModel(ctrl)
        self.alignment       = ExtremumAlignmentTaskAccess(self)
        self.clipping        = ClippingTaskAccess(self)
        self.eventdetection  = EventDetectionTaskAccess(self)
        self.peakselection   = PeakSelectorTaskAccess(self)
        self.singlestrand    = SingleStrandTaskAccess(self)
        self.fittoreference  = FitToReferenceAccess(self)
        self.identification  = FitToHairpinAccess(self)
        if addto:
            self.addto(ctrl, noerase = False)

    def addto(self, ctrl, name = "tasks", noerase = False):
        "set _tasksmodel to same as main"
        super().addto(ctrl, name, noerase)
        self.fittoreference.addto(ctrl, noerase)
        self.identification.addto(ctrl, noerase)
        self.fixedbeads.addto(ctrl, noerase)

    @property
    def availablefixedbeads(self) -> FIXED_LIST:
        "return the availablefixed beads for the current track"
        if self.roottask is None:
            return []
        return self.fixedbeads.current(self._ctrl, self.roottask)

    @property
    def stretch(self) -> float:
        "return the stretch for the current bead"
        dist = self.peaksmodel.display.distances
        est  = self.peaksmodel.config.estimatedstretch
        key  = self.sequencekey
        return getattr(dist.get(key, None), 'stretch', est)

    @property
    def bias(self) -> float:
        "return the bias for the current bead"
        dist = self.peaksmodel.display.distances
        est  = self.peaksmodel.display.estimatedbias
        key  = self.sequencekey
        return getattr(dist.get(key, None), 'bias', est)

    @property
    def sequencekey(self) -> Optional[str]:
        "returns the sequence key"
        dist = self.peaksmodel.display.distances
        tmp  =  min(dist, key = dist.__getitem__) if dist else None
        return self.sequencemodel.display.hpins.get(self.sequencemodel.tasks.bead,
                                                    tmp)

    @sequencekey.setter
    def sequencekey(self, value):
        "sets the new sequence key"
        self.sequencemodel.setnewkey(self._ctrl, value)

    @property
    def constraintspath(self):
        "return the path to constraints"
        return self.peaksmodel.display.constraintspath

    @property
    def useparams(self):
        "return the path to constraints"
        return self.peaksmodel.display.useparams

    @property
    def distances(self) -> Dict[str, Distance]:
        "return the computed distances"
        return self.peaksmodel.display.distances

    @property
    def peaks(self) -> Dict[str, np.ndarray]:
        "return the computed peaks"
        return self.peaksmodel.display.peaks

    @property
    def defaultidenfication(self):
        "returns the default identification task"
        return self.identification.default(self)

    def runbead(self):
        "runs the bead"
        out      = runbead(self.processors(), self.bead)
        tmp, dtl = out if isinstance(out, tuple) else (None, None) # type: ignore

        cpy                    = copy(self)
        cpy.peaksmodel         = copy(self.peaksmodel)
        cpy.peaksmodel.display = copy(self.peaksmodel.display)
        disp = cpy.peaksmodel.display
        if dtl is None:
            disp.distances     = {}
            disp.peaks         = createpeaks(cpy, [])
            disp.estimatedbias = 0.
        else:
            tsk   = cast(PeakSelectorTask, self.peakselection.task)
            peaks = tuple(tsk.details2output(cast(PeakSelectorDetails, dtl)))

            disp.distances     = (getattr(tmp, 'distances')
                                  if self.identification.task else {})
            disp.peaks         = createpeaks(cpy, peaks)
            disp.estimatedbias = disp.peaks['z'][0]
        info = {i: getattr(disp, i) for i in ('distances', 'peaks', 'estimatedbias')}
        self._ctrl.display.update(self.peaksmodel.display, **info)
        if dtl is not None:
            self.sequencemodel.setnewkey(self._ctrl, cpy.sequencekey)

        if isinstance(out, Exception):
            raise out # pylint: disable=raising-bad-type
        return dtl

    def reset(self) -> bool: # type: ignore
        "adds tasks if needed"
        if self.track is None:
            return True

        if self.eventdetection.task is None:
            self.eventdetection.update()

        if self.peakselection.task is None:
            self.peakselection.update()

        self.fittoreference.resetmodel()
        self.identification.resetmodel(self)
        return False

    def setobservers(self, ctrl):
        "observes the global model"
        self.identification.setobservers(self, ctrl)
        self.fittoreference.setobservers(ctrl)

        @ctrl.display.observe(self._tasksmodel.display)
        def _onchangetrack(old = None,  **_):
            if "roottask" in old:
                self._poolcompute()

        @ctrl.tasks.observe("addtask", "updatetask", "removetask")
        def _onchangetasks(**_):
            self._poolcompute()

    def _poolcompute(self, **_):
        if self.peaksmodel.display.nprocessors <= 0:
            return

        root  = self.roottask
        procs = self.processors()
        if procs is None:
            return

        store = procs.data.setCacheDefault(-1, {})
        cache = procs.data.getCache(-1)
        procs = procs.cleancopy()

        def _future(pool, bead):
            fut = pool.submit(runbead, procs, bead)
            return bead, wrap_future(fut)

        async def _iter():
            keys  = set(self.track.beads.keys()) - set(store)
            sleep = self.peaksmodel.display.waittime
            with ProcessPoolExecutor(self.peaksmodel.display.nprocessors) as pool:
                subm = dict(_future(pool, i) for i in keys)
                func = lambda: [i.cancel() for i in subm.values() if not i.done()]
                atexit.register(func)
                while len(subm):
                    await _sleep(sleep)
                    done = {i[0] for i in subm.items() if i[1].done()}
                    for i in set(subm) & set(store):
                        fut = subm.pop(i)
                        if not fut.done():
                            fut.cancel()

                    if len(done):
                        yield [(i, subm.pop(i)) for i in set(done) & set(subm)]

                    if cache() is None or root is not self.roottask:
                        for i in subm.values():
                            i.cancel()
                        break
                pool.shutdown(False)
                atexit.unregister(func)

        async def _thread():
            async for lst in _iter(): # pylint: disable=not-an-iterable
                itms = [(i[0], i[1].result()) for i in lst if not i[1].cancelled()]
                store.update(i for i in itms if i[1] is not None)

        spawn(_thread)
