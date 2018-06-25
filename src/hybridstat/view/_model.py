#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Model for peaksplot"
from typing                     import (Optional, Dict, # pylint: disable=unused-import
                                        List, Tuple, Any, cast)
from   copy                     import deepcopy, copy
import pickle

import numpy                    as     np

from sequences.modelaccess      import SequencePlotModelAccess

from utils                      import updatecopy, initdefaults
from control.modelaccess        import TaskAccess

from cleaning.view              import BeadSubtractionAccess
from eventdetection.processor   import (EventDetectionTask, # pylint: disable=unused-import
                                        ExtremumAlignmentTask)
from model.task                 import RootTask
from model.plots                import PlotModel, PlotTheme, PlotAttrs, PlotDisplay
from peakfinding.histogram      import interpolator
from peakfinding.processor      import PeakSelectorTask # pylint: disable=unused-import
from peakfinding.selector       import PeakSelectorDetails
from peakcalling                import match
from peakcalling.toreference    import ChiSquareHistogramFit
from peakcalling.tohairpin      import Distance
from peakcalling.processor      import (FitToHairpinTask, # pylint: disable=unused-import
                                        FitToReferenceTask)
from peakcalling.processor.fittoreference   import FitData

from ..reporting.batch          import fittohairpintask
from ._processors               import runbead, runrefbead
from ._peakinfo                 import createpeaks

class PeaksPlotTheme(PlotTheme):
    """
    cleaning plot theme
    """
    name            = "hybridstat.peaks.plot"
    figsize         = 500, 750, "fixed"
    xtoplabel       = 'Duration (s)'
    xlabel          = 'Rate (%)'
    widgetsborder   = 10
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

class PeaksPlotConfig:
    "PeaksPlotConfig"
    name             = "hybridstat.peaks"
    estimatedstretch = 1./8.8e-4
    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        pass

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

class FitToReferenceConfig:
    """
    stuff needed to display the FitToReferenceTask
    """
    name          = 'hybridstat.fittoreference'
    histmin       = 1e-4
    peakprecision = 1e-2
    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        pass

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
    name               = 'hybridstat.fittoreference'
    ident        : Any = None
    reference    : Any = None
    fitdata      : Any = _DUMMY
    peaks        : Any = _DUMMY
    interpolator : Any = _DUMMY
    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        pass

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

        ibead = self.bead
        try:
            pks, dtls = runrefbead(self._ctrl, self.reference, ibead)
        except Exception as exc: # pylint: disable=broad-except
            self._ctrl.display.update("message", message = exc)
            pks       = ()

        peaks[ibead] = np.array([i for i, _ in pks], dtype = 'f4')
        if len(pks):
            fits [ibead] = FitData(self.fitalg.frompeaks(pks), (1., 0.)) # type: ignore
            intps[ibead] = interpolator(dtls, miny = self.hmin, fill_value = 0.)

        if args:
            self._ctrl.display.update(self.__store, **args)
        return True, 'ident' in args

class FitToHairpinConfig:
    """
    stuff needed to display the FitToHairpinTask
    """
    name        = 'hybridstat.fittohairpin'
    fit         = FitToHairpinTask.DEFAULT_FIT()
    match       = FitToHairpinTask.DEFAULT_MATCH()
    constraints = deepcopy(FitToHairpinTask.DEFAULT_CONSTRAINTS)

    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        pass

class FitToHairpinAccess(TaskAccess, tasktype = FitToHairpinTask):
    "access to the FitToHairpinTask"
    def __init__(self, mdl):
        super().__init__(mdl)
        self.__defaults = FitToHairpinConfig()

    def addto(self, ctrl, noerase): # pylint: disable=arguments-differ
        "add to the controller"
        self.__defaults = ctrl.theme.add(self.__defaults, noerase)

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

    def default(self, mdl, usr = True):
        "returns the default identification task"
        if isinstance(mdl, str):
            return self._ctrl.theme.get(self.__defaults, mdl, defaultmodel = not usr)

        ols = mdl.oligos
        if ols is None or len(ols) == 0 or len(mdl.sequences(...)) == 0:
            return None

        dist = self.__defaults.fit
        pid  = self.__defaults.match
        cstr = self.__defaults.constraints
        return fittohairpintask(mdl.sequencepath,    ols,
                                mdl.constraintspath, mdl.useparams,
                                constraints = cstr, fit = dist, match = pid)

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

class EventDetectionTaskAccess(TaskAccess, tasktype = EventDetectionTask):
    "access to the EventDetectionTask"

class PeakSelectorTaskAccess(TaskAccess, tasktype = PeakSelectorTask):
    "access to the PeakSelectorTask"

# pylint: disable=too-many-instance-attributes
class PeaksPlotModelAccess(SequencePlotModelAccess):
    "Access to peaks"
    def __init__(self, ctrl, addto = False):
        super().__init__(ctrl)
        self.peaksmodel      = PeaksPlotModel.create(ctrl, False)
        self.subtracted      = BeadSubtractionAccess(self)
        self.alignment       = ExtremumAlignmentTaskAccess(self)
        self.eventdetection  = EventDetectionTaskAccess(self)
        self.peakselection   = PeakSelectorTaskAccess(self)
        self.fittoreference  = FitToReferenceAccess(self)
        self.identification  = FitToHairpinAccess(self)
        if addto:
            self.addto(ctrl, noerase = False)

    def addto(self, ctrl, name = "tasks", noerase = False):
        "set _tasksmodel to same as main"
        super().addto(ctrl, name, noerase)
        self.fittoreference.addto(ctrl, noerase)
        self.identification.addto(ctrl, noerase)


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
        dflt =  min(dist, key = dist.__getitem__) if dist else None
        return self.sequencemodel.display.hpins.get(self.sequencemodel.tasks.bead,
                                                    dflt)

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
        dtl = None
        try:
            tmp, dtl = runbead(self)
        finally:
            cpy = copy(self)
            cpy.peaksmodel = copy(self.peaksmodel)
            cpy.peaksmodel.display = copy(self.peaksmodel.display)
            disp = cpy.peaksmodel.display
            if dtl is None:
                disp.distances     = {}
                disp.peaks         = createpeaks(cpy, [])
                disp.estimatedbias = 0.
            else:
                tsk   = cast(PeakSelectorTask, self.peakselection.task)
                peaks = tuple(tsk.details2output(cast(PeakSelectorDetails, dtl)))

                disp.distances     = tmp.distances if self.identification.task else {}
                disp.peaks         = createpeaks(cpy, peaks)
                disp.estimatedbias = disp.peaks['z'][0]
            info = {i: getattr(disp, i) for i in ('distances', 'peaks', 'estimatedbias')}
            self._ctrl.display.update(self.peaksmodel.display, **info)
            if dtl is not None:
                self.sequencemodel.setnewkey(self._ctrl, cpy.sequencekey)
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
