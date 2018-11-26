#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Model for peaksplot"
from   asyncio                  import sleep as _sleep
from   copy                     import copy, deepcopy
from   multiprocessing          import Process, Pipe
from   typing                   import Optional, Dict, Tuple, Any, Sequence, cast
import pickle

import numpy                    as     np

from control.decentralized      import Indirection
from control.modelaccess        import TaskAccess
from cleaning.view              import DataCleaningModelAccess
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
from utils                      import updatecopy, initdefaults, NoArgs
from view.base                  import spawn
from view.colors                import tohex
from view.plots.base            import themed

from ..reporting.batch          import fittohairpintask
from ._processors               import runbead, runrefbead
from ._peakinfo                 import createpeaks as _createpeaks

# pylint: disable=unused-import,wrong-import-order,ungrouped-imports
from eventdetection.processor.__config__ import EventDetectionTask
from peakfinding.processor.__config__    import PeakSelectorTask, SingleStrandTask
from peakcalling.processor.__config__    import FitToHairpinTask, FitToReferenceTask

class PeaksPlotTheme(PlotTheme):
    """
    cleaning plot theme
    """
    name            = "hybridstat.peaks.plot"
    figsize         = PlotTheme.defaultfigsize(500, 700)
    xtoplabel       = 'Duration (s)'
    xlabel          = 'Rate (%)'
    ntitles         = 4
    count           = PlotAttrs({"dark": 'lightblue', 'basic': 'darkblue'}, 'line', 1)
    eventscount     = PlotAttrs(count.color, 'circle', 3)
    peakscount      = PlotAttrs(count.color, 'triangle', 15, fill_alpha = 0.5,
                                angle = np.pi/2.)
    referencecount  = PlotAttrs('bisque', 'patch', alpha = 0.5)
    peaksduration   = PlotAttrs({"dark": 'lightgreen', 'basic': 'darkgreen'},
                                'diamond', 15, fill_alpha = 0.5, angle = np.pi/2.)
    pkcolors        = dict(dark  = dict(reference       = 'bisque',
                                        missing         = 'red',
                                        found           = 'black'),
                           basic = dict(reference       = 'bisque',
                                        missing         = 'red',
                                        found           = 'gray'))
    toolbar          = dict(PlotTheme.toolbar)
    toolbar['items'] = 'ypan,ybox_zoom,reset,save,tap'
    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        super().__init__(**_)

class PeaksPlotConfig:
    "PeaksPlotConfig"
    def __init__(self):
        self.name:             str   = "hybridstat.peaks"
        self.estimatedstretch: float = 1./8.8e-4
        self.ncpu:             int   = 0
        self.waittime:         float = .1

class PeaksPlotDisplay(PlotDisplay):
    "PeaksPlotDisplay"
    name                              = "hybridstat.peaks"
    distances : Dict[str, Distance]   = dict()
    peaks:      Dict[str, np.ndarray] = dict()
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

class FitToReferenceConfig:
    """
    stuff needed to display the FitToReferenceTask
    """
    def __init__(self):
        self.name          : str   = 'hybridstat.fittoreference'
        self.histmin       : float = 1e-4
        self.peakprecision : float = 1e-2

_DUMMY = type('_DummyDict', (),
              dict(get          = lambda *_: None,
                   __contains__ = lambda _: False,
                   __len__      = lambda _: 0,
                   __iter__     = lambda _: iter(())))()
class FitToReferenceStore:
    """
    stuff needed to display the FitToReferenceTask
    """
    DEFAULTS = dict(ident        = None,   reference = None,
                    fitdata      = _DUMMY, peaks     = _DUMMY,
                    interpolator = _DUMMY)
    def __init__(self, reference = None):
        self.name         : str                 = 'hybridstat.fittoreference'
        self.ident        : Optional[bytes]     = None
        self.reference    : Optional[RootTask]  = reference
        self.refcache     : Dict[RootTask, Any] = {}
        self.fitdata      : Dict[RootTask, Any] = {}
        self.peaks        : Dict[RootTask, Any] = {}
        self.interpolator : Dict[RootTask, Any] = {}

class FitToReferenceAccess(TaskAccess, tasktype = FitToReferenceTask):
    "access to the FitToReferenceTask"
    __store = Indirection()
    __theme = Indirection()
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
            self._ctrl.display.update(self.__store, **info)

    @property
    def referencepeaks(self) -> Optional[np.ndarray]:
        "returns reference peaks"
        # pylint: disable=no-member
        pks = self.__store.peaks.get(self.bead, None)
        return None if pks is None or len(pks) == 0 else pks

    def setobservers(self, ctrl):
        "observes the global model"
        def _onref(old = None, **_):
            if 'reference' in old:
                self.resetmodel()
        type(self).__store.observe(ctrl, self, _onref)

        def _ontask(parent = None, **_):
            if parent == self.reference:
                info = FitToReferenceStore(reference = self.reference).__dict__
                info.pop('name')
                ctrl.display.update(self.__store, **info)
                self.resetmodel()
        ctrl.tasks.observe("updatetask", "addtask", "removetask", _ontask)

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

    def __computefitdata(self) -> bool:
        args  = {} # type: Dict[str, Any]
        ident = pickle.dumps(tuple(self._ctrl.tasks.tasklist(self.reference)))
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
        except Exception as exc: # pylint: disable=broad-except
            self._ctrl.display.update("message", message = exc)

        peaks[ibead] = np.array([i for i, _ in pks], dtype = 'f4')
        if len(pks):
            fits [ibead] = FitData(self.fitalg.frompeaks(pks), (1., 0.)) # type: ignore
            intps[ibead] = interpolator(dtls, miny = self.hmin, fill_value = 0.)

        if args:
            self._ctrl.display.update(self.__store, **args)
        return True

class FitToHairpinConfig:
    """
    stuff needed to display the FitToHairpinTask
    """
    def __init__(self):
        cls                                  = FitToHairpinTask
        self.name        : str               = 'hybridstat.fittohairpin'
        self.fit         : HairpinFitter     = cls.DEFAULT_FIT()
        self.match       : PeakMatching      = cls.DEFAULT_MATCH()
        self.constraints : Dict[str, Range]  = deepcopy(cls.DEFAULT_CONSTRAINTS)
        self.stretch     : Tuple[float, int] = (5.,   1)
        self.bias        : Tuple[float, int] = (5e-3, 1)

ConstraintsDict = Dict[RootTask, Constraints]
class FitToHairpinDisplay:
    """
    stuff needed to display the FitToHairpinTask
    """
    def __init__(self):
        self.name:        str             = 'hybridstat.fittohairpin'
        self.constraints: ConstraintsDict = {}

class FitToHairpinAccess(TaskAccess, tasktype = FitToHairpinTask):
    "access to the FitToHairpinTask"
    __defaults = Indirection()
    __display  = Indirection()
    def __init__(self, mdl):
        super().__init__(mdl)
        self.__defaults = FitToHairpinConfig()
        self.__display  = FitToHairpinDisplay()

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

        self._ctrl.display.update(self.__display, constraints = cstrs)
        if  self.task is not None:
            self.update(constraints = {i: dict(j) for i, j in cstrs.items()})

    def constraints(self,
                    root: Optional[RootTask] = None,
                    bead: Optional[int]      = None
                   ) -> Tuple[Optional[str], Optional[float], Optional[float]]:
        "returns the constraints"
        root = self.roottask if root is None else root
        bead = self.bead     if bead is None else bead
        if root is None or bead is None:
            return None, None, None

        # pylint: disable=no-member
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
        type(self).__defaults.observe(ctrl, self, _observe)
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
    __config = Indirection()
    def __init__(self, mdl):
        super().__init__(mdl)
        self.__config = SingleStrandConfig()

    def setobservers(self, mdl, ctrl):
        "observes the global model"
        ctrl.theme.observe(self.__config, lambda **_: mdl.reset())

    def resetmodel(self, mdl):
        "resets the model"
        self.update(disabled = not (self.__config.automated and mdl.hassinglestrand))

# pylint: disable=too-many-instance-attributes
class PeaksPlotModelAccess(SequencePlotModelAccess, DataCleaningModelAccess):
    "Access to peaks"
    def __init__(self, ctrl, addto = False):
        DataCleaningModelAccess.__init__(self, ctrl)
        SequencePlotModelAccess.__init__(self, ctrl)
        self.peaksmodel     = PeaksPlotModel.create(ctrl, False)
        self.eventdetection = EventDetectionTaskAccess(self)
        self.peakselection  = PeakSelectorTaskAccess(self)
        self.singlestrand   = SingleStrandTaskAccess(self)
        self.fittoreference = FitToReferenceAccess(self)
        self.identification = FitToHairpinAccess(self)

        self.peaksmodel.display.peaks = _createpeaks(self, [])
        if addto:
            self.addto(ctrl, noerase = False)

    def getfitparameters(self, key = NoArgs) -> Tuple[float, float]:
        "return the stretch  & bias for the current bead"
        if key is not None:
            dist = self.peaksmodel.display.distances
            key  = self.sequencekey if key is NoArgs else key
            if key in dist:
                return dist[key][1:]

        out = self.identification.constraints()[1:]
        if out[0] is None:
            out = self.peaksmodel.config.estimatedstretch, out[1]
        if out[1] is None:
            out = out[0], self.peaksmodel.display.estimatedbias
        return cast(Tuple[float, float], out)

    @property
    def stretch(self) -> float:
        "return the stretch for the current bead"
        return self.getfitparameters()[0]

    @property
    def bias(self) -> float:
        "return the bias for the current bead"
        return self.getfitparameters()[1]

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
        out      = runbead(self.processors(),
                           self.bead,
                           self.fittoreference.refcache)
        tmp, dtl = out if isinstance(out, tuple) else (None, None) # type: ignore

        cpy                    = copy(self)
        cpy.peaksmodel         = copy(self.peaksmodel)
        cpy.peaksmodel.display = copy(self.peaksmodel.display)
        disp = cpy.peaksmodel.display
        if dtl is None:
            disp.distances     = {}
            disp.peaks         = _createpeaks(cpy, [])
            disp.estimatedbias = 0.
        else:
            tsk   = cast(PeakSelectorTask, self.peakselection.task)
            peaks = tuple(tsk.details2output(cast(PeakSelectorDetails, dtl)))

            disp.distances     = (getattr(tmp, 'distances')
                                  if self.identification.task else {})
            disp.peaks         = _createpeaks(cpy, peaks)
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
        self.singlestrand.resetmodel(self)
        return False

    def setobservers(self, ctrl):
        "observes the global model"
        self.identification.setobservers(self, ctrl)
        self.fittoreference.setobservers(ctrl)
        self.singlestrand.setobservers(self, ctrl)

        @ctrl.display.observe(self._tasksdisplay)
        def _onchangetrack(old = None,  **_):
            if "roottask" in old:
                self._poolcompute()

        @ctrl.tasks.observe("addtask", "updatetask", "removetask")
        def _onchangetasks(**_):
            self._poolcompute()

    @staticmethod
    def _poolrun(pipe, procs, refcache, keys):
        for bead in keys:
            out = runbead(procs, bead, refcache)
            pipe.send((bead, out, refcache.get(bead, None)))
            if pipe.poll():
                return
        pipe.send((None, None, None))

    def _poolcompute(self, **_):
        if self.peaksmodel.config.ncpu <= 0:
            return

        root  = self.roottask
        procs = self.processors()
        if procs is None:
            return

        store = procs.data.setCacheDefault(-1, {})
        cache = procs.data.getCache(-1)
        procs = procs.cleancopy()
        refc  = self.fittoreference.refcache

        async def _iter():
            keys    = np.array(list(set(self.track.beads.keys()) - set(store)))
            nkeys   = len(keys)
            ncpu    = min(nkeys, self.peaksmodel.config.ncpu)
            jobs    = ([keys] if ncpu == 1 else
                       np.split(keys, list(range(nkeys//ncpu+1, nkeys, nkeys//ncpu+1))))
            pipes   = [Pipe() for i in range(len(jobs))]
            process = [Process(target = self._poolrun,
                               args   = (pipe[1], procs, refc, job))
                       for pipe, job in zip(pipes, jobs)]
            for _ in process:
                _.start()
            out    = [True]
            while out[0] is not None:
                await _sleep(self.peaksmodel.config.waittime)
                for pipe, _ in pipes:
                    while pipe.poll() and cache() is not None and root is self.roottask:
                        out = pipe.recv()
                        if out[0] is None:
                            break

                        if out[0] not in store:
                            yield out

                if out[0] is not None and cache() is None or root is not self.roottask:
                    for pipe, _ in pipes:
                        pipe.send(True)
                    break

        async def _thread():
            async for bead, itms, ref in _iter(): # pylint: disable=not-an-iterable
                store[bead] = itms
                if ref is not None:
                    refc[bead]  = ref

        spawn(_thread)

def createpeaks(mdl, themecolors, vals) -> Dict[str, np.ndarray]:
    "create the peaks ColumnDataSource"
    colors = [tohex(themed(mdl.themename, themecolors)[i])
              for i in ('found', 'missing', 'reference')]

    peaks          = dict(mdl.peaks)
    peaks['color'] = [colors[0]]*len(peaks.get('id', ()))
    if vals is not None and mdl.identification.task is not None and len(mdl.distances):
        for key in mdl.sequences(...):
            peaks[key+'color'] = np.where(np.isfinite(peaks[key+'id']), *colors[:2])
            if key == mdl.sequencekey:
                peaks['color'] = peaks[mdl.sequencekey+'color']
    elif mdl.fittoreference.referencepeaks is not None:
        peaks['color'] = np.where(np.isfinite(peaks['id']), colors[2], colors[0])
    return peaks
