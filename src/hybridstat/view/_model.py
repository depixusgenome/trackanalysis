#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Model for peaksplot"
from typing                     import Optional, Dict, Any, Tuple, cast
from itertools                  import product
import pickle

import numpy                    as     np

from sequences.modelaccess      import (SequencePlotModelAccess,
                                        FitParamProp    as _FitParamProp,
                                        SequenceKeyProp as _SequenceKeyProp)

from utils                      import updatecopy
from control.modelaccess        import PROPS, TaskAccess
from control.processor          import processors, Processor

from model.task                 import RootTask
from eventdetection.processor   import EventDetectionTask, ExtremumAlignmentTask
from peakfinding.histogram      import Interpolator
from peakfinding.processor      import PeakSelectorTask
from peakfinding.probabilities  import Probability
from peakcalling.tohairpin      import Distance
from peakcalling.processor      import (FitToHairpinTask, FitToHairpinProcessor,
                                        FitToReferenceTask, FitBead)
from peakcalling.processor.fittoreference   import FitData

from ..reporting.batch          import fittohairpintask

class FitToReferenceAccess(TaskAccess):
    "access to the FitToReferenceTask"
    def __init__(self, ctrl):
        super().__init__(ctrl, FitToReferenceTask)
        self.__store.defaults           = dict(id = None, cache = {}, reference = None)
        self.configtask.histmin.default = 1e-3

    @staticmethod
    def _configattributes(kwa):
        return {}

    @property
    def __store(self):
        return self.project.fittoreference.gui

    def __setconfig(self, ident, cache, ref):
        self.__store.update(id        = ident,
                            cache     = cache,
                            reference = ref)

    __params = property(lambda self: self.__store.cache)
    __ref    = property(lambda self: self.__store.reference)
    __id     = property(lambda self: self.__store.id)

    @property
    def params(self) -> Optional[Tuple[float, float]]:
        "returns the computed stretch or 1."
        tsk = cast(FitToReferenceTask, self.task)
        if tsk is None:
            return None

        ibead = self.bead
        if ibead not in tsk.fitdata:
            return 1., 0.

        return self.__params.get().get(ibead, None)

    @params.setter
    def params(self, vals):
        self.__params.get()[self.bead] = tuple(vals)

    stretch = property(lambda self: self.params[0])
    bias    = property(lambda self: self.params[1])
    hmin    = property(lambda self: self.configtask.histmin.get())

    def remove(self):
        "removes the task"
        self.__store.update(id = None, cache = {}, reference = None)
        super().remove()

    def update(self, **_):
        "removes the task"
        assert len(_) == 0
        ident, fitdata = self.__computefitdata()
        if fitdata is None:
            return

        if ident == self.__id.get():
            self.__store.update(id = ident)
        else:
            self.__store.update(id = ident, cache = {})
        super().update(fitdata = fitdata)

    @property
    def reference(self) -> Optional[RootTask]:
        "returns the current reference"
        return self.__ref.get()

    @reference.setter
    def reference(self, value:Optional[RootTask]):
        "sets the current reference"
        if value is not self.__ref.get():
            return self.remove() if value in (None, self.roottask) else self.update()

    def resetmodel(self):
        "adds a bead to the task"
        ref = self.__ref.get()
        if self.task is None and ref in (self.roottask, None):
            return
        return self.remove() if ref is self.roottask else self.update()

    def refhistogram(self, xaxis):
        "returns the histogram interpolated to the provided values"
        task  = self.task
        ibead = self.bead
        if task is None or ibead not in task.fitdata:
            return np.full(len(xaxis), np.NaN, dtype = 'f4')

        return Interpolator(task.fitdata[ibead].data, self.hmin)(xaxis)

    def __computefitdata(self):
        ibead = self.bead
        task  = cast(FitToReferenceTask, self.task)
        ident = pickle.dumps(tuple(self._ctrl.tasks(self.reference)))
        if self.__id.get() == ident:
            if ibead in task.fitdata:
                return None, None
            fits = dict(task.fitdata)
        else:
            fits = dict()

        peaks       = next(iter(self._ctrl.run(self.reference, EventDetectionTask,
                                               copy = True)))
        fits[ibead] = FitData(task.fitalg.frompeaks(peaks[ibead,...]), (1., 0.))
        return ident, fits

class FitToHairpinAccess(TaskAccess):
    "access to the FitToHairpinTask"
    def __init__(self, ctrl):
        super().__init__(ctrl, FitToHairpinTask)
        self.__defaults = self.config.root.tasks.fittohairpin
        self.__defaults.defaults = {'fit':   FitToHairpinTask.DEFAULT_FIT(),
                                    'match': FitToHairpinTask.DEFAULT_MATCH()}

    def setobservers(self, mdl):
        "observes the global model"
        def _observe(_):
            task = mdl.defaultidenfication
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

    def default(self, mdl):
        "returns the default identification task"
        if isinstance(mdl, str):
            return self.__defaults[mdl].get()

        ols = mdl.oligos
        if ols is None or len(ols) == 0 or len(mdl.sequences(...)) == 0:
            return None

        dist = self.__defaults.fit.get()
        pid  = self.__defaults.match.get()
        return fittohairpintask(mdl.sequencepath,    ols,
                                mdl.constraintspath, mdl.useparams,
                                fit = dist, match = pid)

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
        self.fits : FitBead                 = None
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

    @property
    def distances(self) -> Dict[str, Distance]:
        "returns the distances which were computed"
        return self.fits.distances if self.fits is not None else {}

    def setpeaks(self, dtl) -> Dict[str, Any]:
        "sets current bead peaks and computes the fits"
        if dtl is None:
            self.peaks = dict.fromkeys(('z', 'id', 'distance', 'sigma', 'bases',
                                        'duration', 'count', 'skew'), [])
            self.fits  = None
            return self.peaks

        tsk        = cast(PeakSelectorTask, self.peakselection.task)
        peaks      = tuple(tsk.details2output(dtl))
        nan        = lambda: np.full((len(peaks),), np.NaN, dtype = 'f4')
        self.peaks = dict(z        = np.array([i for i, _ in peaks], dtype = 'f4'),
                          sigma    = nan(),
                          skew     = nan(),
                          duration = nan(),
                          count    = nan())

        self.estimatedbias  = self.peaks['z'][0]

        self.__set_ids_and_distances(peaks)
        self.__set_probas(peaks)
        return self.peaks

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

    def __set_ids_and_distances(self, peaks):
        task  = self.identification.task
        dico  = self.peaks
        names = 'bases', 'id', 'distance', 'orient'
        nan   = np.full((len(peaks),), np.NaN, dtype = 'f4')

        dico.update(**dict.fromkeys(names, nan))
        dico['orient'] = np.array([' '] * len(nan))

        if task is None:
            dico['bases']  = (dico['z']-self.bias)*self.stretch
            return

        self.fits = FitToHairpinProcessor.compute((self.bead, peaks), # type: ignore
                                                  **task.config())[1]

        for key in product(self.sequences(...), names):
            dico[''.join(key)] = np.copy(dico[key[1]])

        strori  = self.css.stats.title.orientation.get()
        alldist = self.distances
        for key, hyb in self.hybridisations(...).items():
            if key not in alldist:
                continue

            dist = alldist[key].stretch, alldist[key].bias
            tmp  = task.match[key].pair(dico['z'], *dist)['key']
            good = tmp >= 0
            ori  = dict(hyb)

            dico[f'{key}bases']          = (dico['z'] - dist[1])*dist[0]
            dico[f'{key}id']      [good] = tmp[good]
            dico[f'{key}distance'][good] = (tmp - dico[f'{key}bases'])[good]
            dico[f'{key}orient']  [good] = [strori[ori.get(int(i+0.01), 2)]
                                            for i in dico[f'{key}id'][good]]
        for i in names:
            dico[i] = dico[self.sequencekey+i]

    def __set_probas(self, peaks):
        task = self.eventdetection.task
        prob = Probability(framerate   = self.track.framerate,
                           minduration = task.events.select.minduration)
        dur  = self.track.phaseduration(..., task.phase)
        for i, (_, evts) in enumerate(peaks):
            val                       = prob(evts, dur)
            self.peaks['duration'][i] = val.averageduration
            self.peaks['sigma'][i]    = prob.resolution(evts)
            self.peaks['count'][i]    = min(100., val.hybridisationrate*100.)
            self.peaks['skew'][i]     = np.nanmedian(prob.skew(evts))
