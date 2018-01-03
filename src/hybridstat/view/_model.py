#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Model for peaksplot"
from typing                     import (Optional, Dict, # pylint: disable=unused-import
                                        List, Tuple, Any, cast)
from   copy                     import deepcopy
import pickle

import numpy                    as     np

from sequences.modelaccess      import (SequencePlotModelAccess,
                                        FitParamProp    as _FitParamProp,
                                        SequenceKeyProp as _SequenceKeyProp)

from utils                      import updatecopy
from control.modelaccess        import PROPS, TaskAccess

from model.task                 import RootTask
from eventdetection.processor   import EventDetectionTask, ExtremumAlignmentTask
from peakfinding.histogram      import interpolator
from peakfinding.processor      import PeakSelectorTask
from peakfinding.selector       import PeakSelectorDetails
from peakcalling                import match
from peakcalling.toreference    import ChiSquareHistogramFit
from peakcalling.tohairpin      import Distance
from peakcalling.processor      import FitToHairpinTask, FitToReferenceTask
from peakcalling.processor.fittoreference   import FitData

from ..reporting.batch          import fittohairpintask
from ._processors               import runbead, runrefbead
from ._peakinfo                 import createpeaks

_DUMMY = type('_DummyDict', (),
              dict(get          = lambda *_: None,
                   __contains__ = lambda _: False,
                   __len__      = lambda _: 0,
                   __iter__     = lambda _: iter(())))()

class FitToReferenceAccess(TaskAccess):
    "access to the FitToReferenceTask"
    __DEFAULTS = dict(id           = None,   reference = None,
                      fitdata      = _DUMMY, peaks     = _DUMMY,
                      interpolator = _DUMMY)
    def __init__(self, ctrl):
        super().__init__(ctrl, FitToReferenceTask)
        self.__store             = self.project.root.tasks.fittoreference.gui
        self.__store.defaults    = self.__DEFAULTS

        self.configtask.defaults = dict(histmin = 1e-4, peakprecision = 1e-2)

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
    hmin    = property(lambda self: self.configtask.histmin.get())

    def update(self, **_):
        "removes the task"
        assert len(_) == 0
        newdata, newid = self.__computefitdata()
        if not newdata:
            return

        # pylint: disable=not-callable
        cache = None if newid else self.cache()
        super().update(fitdata = self.__store.fitdata.get())
        if cache:
            self._ctrl.processors(self.roottask).data.setCacheDefault(self.task, cache)

    @property
    def reference(self) -> Optional[RootTask]:
        "returns the root task for the reference data"
        return self.__store.reference.get()

    @reference.setter
    def reference(self, val):
        "sets the root task for the reference data"
        if val is not self.reference:
            info = dict(self.__DEFAULTS)
            info['reference'] = val
            self.__store.update(**info)

    def setobservers(self, _):
        "observes the global model"
        self.__store.reference.observe(lambda _: self.resetmodel())

    def resetmodel(self):
        "adds a bead to the task"
        return (self.update() if self.reference not in (self.roottask, None) else
                self.remove() if self.task                                     else
                None)

    def refhistogram(self, xaxis):
        "returns the histogram interpolated to the provided values"
        intp = self.__store.interpolator.get().get(self.bead, None)
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
            ids = match.compute(ref, peaks, self.configtask.peakprecision.get())
            arr[ids[:,1]] = ref[ids[:,0]]
        return arr

    @staticmethod
    def _configattributes(_):
        return {}

    @property
    def referencepeaks(self) -> Optional[np.ndarray]:
        "returns reference peaks"
        pks = self.__store.peaks.get().get(self.bead, None)
        return None if pks is None or len(pks) == 0 else pks

    def __computefitdata(self) -> Tuple[bool, bool]:
        args  = {} # type: Dict[str, Any]
        ident = pickle.dumps(tuple(self._ctrl.tasks(self.reference)))
        if self.__store.id.get() == ident:
            if self.referencepeaks is not None:
                return False, False
        else:
            args['id'] = ident

        fits  = self.__store.fitdata.get()
        if not fits:
            args['fitdata'] = fits = {}

        peaks  = self.__store.peaks.get()
        if not peaks:
            args['peaks'] = peaks = {}

        intps  = self.__store.interpolator.get()
        if not intps:
            args['interpolator'] = intps = {}

        ibead = self.bead
        try:
            pks, dtls = runrefbead(self._ctrl, self.reference, ibead)
        except Exception as exc: # pylint: disable=broad-except
            self.config.message.set(exc)
            pks       = ()

        peaks[ibead] = np.array([i for i, _ in pks], dtype = 'f4')
        if len(pks):
            fits [ibead] = FitData(self.fitalg.frompeaks(pks), (1., 0.)) # type: ignore
            intps[ibead] = interpolator(dtls, miny = self.hmin, fill_value = 0.)

        if args:
            self.__store.update(**args)
        return True, 'id' in args

class FitToHairpinAccess(TaskAccess):
    "access to the FitToHairpinTask"
    def __init__(self, ctrl):
        super().__init__(ctrl, FitToHairpinTask)
        self.__defaults = self.config.root.tasks.fittohairpin
        self.__defaults.defaults = {'fit':         FitToHairpinTask.DEFAULT_FIT(),
                                    'match':       FitToHairpinTask.DEFAULT_MATCH(),
                                    'constraints': deepcopy(FitToHairpinTask.DEFAULT_CONSTRAINTS)}

    def setobservers(self, mdl):
        "observes the global model"
        def _observe(_):
            task = self.default(mdl)
            if task is None:
                self.remove()
            else:
                self.update(**task.config())

        mdl.observeprop('oligos', 'sequencepath', 'constraintspath', 'useparams',
                        'config.root.tasks.fittohairpin.fit',
                        'config.root.tasks.fittohairpin.match',
                        _observe)

    @staticmethod
    def _configattributes(kwa):
        return {}

    def updatedefault(self, attr, inst = None, **kwa):
        "updates the identifiers for this task"
        if inst is None and len(kwa) == 0:
            return

        cnf  = self.__defaults[attr]
        inst = (inst() if isinstance(inst, type) else
                inst   if inst is not None       else
                cnf.get())
        cnf.set(updatecopy(inst, **kwa))

    def default(self, mdl, usr = True):
        "returns the default identification task"
        if isinstance(mdl, str):
            tmp = self.__defaults[mdl]
            return tmp.get() if usr else tmp.getdefault()

        ols = mdl.oligos
        if ols is None or len(ols) == 0 or len(mdl.sequences(...)) == 0:
            return None

        dist = self.__defaults.fit.get()
        pid  = self.__defaults.match.get()
        cstr = self.__defaults.constraints.get()
        return fittohairpintask(mdl.sequencepath,    ols,
                                mdl.constraintspath, mdl.useparams,
                                constraints = cstr, fit = dist, match = pid)

    def resetmodel(self, mdl):
        "resets the model"
        task = self.default(mdl)
        cur  = self.task
        if task is None and cur is not None:
            self.remove()
        elif task != cur:
            self.update(**task.config())

class FitParamProp(_FitParamProp):
    "access to bias or stretch"
    def __get__(self, obj, tpe) -> Optional[float]: # type: ignore
        if obj is not None:
            dist = obj.distances.get(obj.sequencekey, None)
            if dist is not None:
                return getattr(dist, self._key)
        return super().__get__(obj, tpe)

class SequenceKeyProp(_SequenceKeyProp):
    "access to the sequence key"
    def __get__(self, obj, tpe) -> Optional[str]:
        "returns the current sequence key"
        if obj is not None and len(obj.distances) and self.fromglobals(obj) is None:
            if len(obj.distances):
                return min(obj.distances, key = obj.distances.__getitem__)
        return super().__get__(obj, tpe)

class PeaksPlotModelAccess(SequencePlotModelAccess):
    "Access to peaks"
    def __init__(self, ctrl, key: str = None) -> None:
        if key is None:
            key = '.plot.peaks'
        super().__init__(ctrl, key)
        self.config.root.tasks.extremumalignment.default = ExtremumAlignmentTask()

        self.eventdetection                 = TaskAccess(self, EventDetectionTask)
        self.peakselection                  = TaskAccess(self, PeakSelectorTask)
        self.distances : Dict[str, Distance]= dict()
        self.peaks: Dict[str, np.ndarray]   = dict()
        self.estimatedbias                  = 0.
        self.fittoreference                 = FitToReferenceAccess(self)
        self.identification                 = FitToHairpinAccess(self)

        cls = type(self)
        cls.constraintspath .setdefault(self, None) # type: ignore
        cls.useparams       .setdefault(self, True) # type: ignore
        cls.sequencekey     .setdefault(self, None) # type: ignore
        cls.stretch         .setdefault(self)       # type: ignore
        cls.bias            .setdefault(self)       # type: ignore

    sequencekey     = cast(Optional[str],   SequenceKeyProp())
    stretch         = cast(Optional[float], FitParamProp('stretch'))
    bias            = cast(Optional[float], FitParamProp('bias'))
    constraintspath = cast(Optional[str],   PROPS.projectroot('constraints.path'))
    useparams       = cast(bool,            PROPS.projectroot('constraints.useparams'))

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
            if dtl is None:
                self.distances     = {}
                self.peaks         = createpeaks(self, [])
                self.estimatedbias = 0.
            else:
                tsk   = cast(PeakSelectorTask, self.peakselection.task)
                peaks = tuple(tsk.details2output(cast(PeakSelectorDetails, dtl)))

                self.distances     = tmp.distances if self.identification.task else {}
                self.peaks         = createpeaks(self, peaks)
                self.estimatedbias = self.peaks['z'][0]
        return dtl

    def reset(self) -> bool: # type: ignore
        "adds tasks if needed"
        if self.track is None or self.checkbead(False):
            return True

        if self.eventdetection.task is None:
            self.eventdetection.update()

        if self.peakselection.task is None:
            self.peakselection.update()

        self.fittoreference.resetmodel()
        self.identification.resetmodel(self)
        return False

    def observe(self):
        "observes the global model"
        self.identification.setobservers(self)
        self.fittoreference.setobservers(self)
