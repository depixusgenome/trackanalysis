#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Model for peaksplot"
from typing                     import Optional, Sequence, Dict
from itertools                  import product

import numpy                    as     np

import sequences
from control.processor          import processors
from eventdetection.processor   import EventDetectionTask, ExtremumAlignmentTask
from peakfinding.processor      import PeakSelectorTask
from peakfinding.probabilities  import Probability
from peakcalling.processor      import (FitToHairpinTask, FitToHairpinProcessor,
                                        FitBead, Distance)

from view.plots.tasks           import TaskPlotModelAccess, TaskAccess
from view.plots.sequence        import (readsequence,
                                        FitParamProp    as _FitParamProp,
                                        SequenceKeyProp as _SequenceKeyProp)

from ..reporting.batch          import fittohairpintask

class FitToHairpinAccess(TaskAccess):
    "access to the FitToHairpinTask"
    def __init__(self, ctrl):
        super().__init__(ctrl, FitToHairpinTask)

    @staticmethod
    def _configattributes(kwa):
        return {}

class FitParamProp(_FitParamProp):
    "access to bias or stretch"
    def __get__(self, obj, tpe) -> Optional[str]:
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

class IdentificationModelAccess(TaskPlotModelAccess):
    "Access to identification"
    def __init__(self, ctrl, key: Optional[str] = None) -> None:
        if key is None:
            key = '.plot.peaks'
        super().__init__(ctrl, key)
        self.identification = FitToHairpinAccess(self)

        cls = type(self)
        cls.sequencepath    .setdefault(self, None)
        cls.oligos          .setdefault(self, [], size = 4)
        cls.constraintspath .setdefault(self, None)
        cls.useparams       .setdefault(self, True)

    props           = TaskPlotModelAccess.props
    sequencepath    = props.configroot[Optional[str]]('last.path.sequence')
    oligos          = props.configroot[Optional[Sequence[str]]]('oligos')
    constraintspath = props.projectroot[Optional[str]]('constraints.path')
    useparams       = props.projectroot[bool]('constraints.useparams')
    @property
    def sequences(self):
        "returns current sequences"
        return readsequence(self.sequencepath)

    @property
    def defaultidenfication(self):
        "returns the default identification task"
        ols = self.oligos
        if ols is None or len(ols) == 0 or len(self.sequences) == 0:
            return None
        else:
            return fittohairpintask(self.sequencepath,    ols,
                                    self.constraintspath, self.useparams)

class PeaksPlotModelAccess(IdentificationModelAccess):
    "Access to peaks"
    def __init__(self, ctrl, key: Optional[str] = None) -> None:
        super().__init__(ctrl, key)
        self.config.root.tasks.extremumalignment.default = ExtremumAlignmentTask()

        self.eventdetection     = TaskAccess(self, EventDetectionTask)
        self.peakselection      = TaskAccess(self, PeakSelectorTask)
        self.fits               = None   # type: Optional[FitBead]
        self.peaks              = dict() # type: Dict[str, np.ndarray]
        self.estimatedbias      = 0.

        cls = type(self)
        cls.sequencekey .setdefault(self, None) # type: ignore
        cls.stretch     .setdefault(self)       # type: ignore
        cls.bias        .setdefault(self)       # type: ignore

    sequencekey  = SequenceKeyProp()
    stretch      = FitParamProp('stretch')
    bias         = FitParamProp('bias')

    @property
    def distances(self) -> Dict[str, Distance]:
        "returns the distances which were computed"
        return self.fits.distances if self.fits is not None else {}

    def setpeaks(self, dtl) -> Optional[FitBead]:
        "sets current bead peaks and computes the fits"
        if dtl is None:
            self.peaks = dict.fromkeys(('z', 'id', 'distance', 'sigma', 'bases',
                                        'duration', 'count'), [])
            self.fits  = None
            return

        nan        = lambda: np.full((len(peaks),), np.NaN, dtype = 'f4')
        peaks      = tuple(self.peakselection.task.details2output(dtl))
        self.peaks = dict(z        = np.array([i for i, _ in peaks], dtype = 'f4'),
                          sigma    = nan(),
                          duration = nan(),
                          count    = nan())

        self.estimatedbias  = self.peaks['z'][0]

        self.__set_ids_and_distances(peaks)
        self.__set_probas(peaks)

        return self.peaks

    def runbead(self):
        "returns a tuple (dataitem, bead) to be displayed"
        if self.track is None or self.checkbead(False):
            return None

        root  = self.roottask
        ibead = self.bead
        task  = self.eventdetection.task
        if task is None:
            task  = self.config.tasks.eventdetection.get()
            ind   = self.eventdetection.index
            beads = next(iter(self._ctrl.run(root, ind-1, copy = True)))
            return next(processors(task)).apply(beads, **task.config())[ibead, ...]
        else:
            return next(iter(self._ctrl.run(root, task, copy = True)))[ibead, ...]

    def reset(self) -> bool:
        "adds tasks if needed"
        if self.track is None or self.checkbead(False):
            return True

        if self.eventdetection.task is None:
            self.eventdetection.update()

        if self.peakselection.task is None:
            self.peakselection.update()

        task = self.defaultidenfication
        cur  = self.identification.task
        if task is None and cur is not None:
            self.identification.remove()
        elif task is not None and cur is None:
            self.identification.update(**task.config())
        return False

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

        self.fits = FitToHairpinProcessor.compute((self.bead, peaks),
                                                  **task.config())[1]

        for key in product(self.sequences, names):
            dico[''.join(key)] = np.copy(dico[key[1]])

        strori  = self.css.stats.title.orientation.get()
        alldist = self.distances
        for key, seq in self.sequences.items():
            if key not in alldist:
                continue

            dist = alldist[key].stretch, alldist[key].bias
            tmp  = task.peakids[key].pair(dico['z'], *dist)['key']
            good = tmp >= 0
            ori  = dict(sequences.peaks(seq, self.oligos))

            dico[key+'bases']          = (dico['z'] - dist[1])*dist[0]
            dico[key+'id']      [good] = tmp[good]
            dico[key+'distance'][good] = (tmp - dico[key+'bases'])[good]
            dico[key+'orient']  [good] = [strori[ori.get(int(i+0.01), 2)]
                                          for i in dico[key+'id'][good]]

        for key in names:
            dico[key] = dico[self.sequencekey+key]

    def __set_probas(self, peaks):
        task = self.eventdetection.task
        prob = Probability(framerate   = self.track.framerate,
                           minduration = task.events.select.minduration)
        dur  = self.track.phaseduration(..., task.phase)
        for i, (_, evts) in enumerate(peaks):
            val                       = prob(evts, dur)
            self.peaks['duration'][i] = val.averageduration
            self.peaks['sigma'][i]    = prob.resolution(evts)
            self.peaks['count'][i]    = min(100., val.hybridizationrate*100.)
