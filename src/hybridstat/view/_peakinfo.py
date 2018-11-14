#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Creating a dictionnary with all peak related stuff"
from typing                     import Dict, List, TYPE_CHECKING, cast
from abc                        import ABC, abstractmethod
from itertools                  import product

import numpy                    as     np

from eventdetection.processor   import EventDetectionTask
from peakfinding.probabilities  import Probability

if TYPE_CHECKING:
    from ._model                import PeaksPlotModelAccess # pylint: disable=unused-import

class PeakInfo(ABC):
    "Creates a peaks info dictionnary"
    @abstractmethod
    def keys(self, mdl: 'PeaksPlotModelAccess') -> List[str]:
        "returns the list of keys"

    @abstractmethod
    def values(self, mdl: 'PeaksPlotModelAccess', peaks, dico: Dict[str, np.ndarray]):
        "sets current bead peaks and computes the fits"

    def defaults(self, mdl, peaks) -> Dict[str, np.ndarray]:
        "sets current bead peaks and computes the fits"
        size = len(peaks)
        return {i: np.full(size, np.NaN, dtype = 'f4') for i in self.keys(mdl)}

class ZPeakInfo(PeakInfo):
    "All base peak-related info"
    @staticmethod
    def keys(mdl: 'PeaksPlotModelAccess') -> List[str]:
        "returns the list of keys"
        return ['z']

    @staticmethod
    def values(mdl: 'PeaksPlotModelAccess', peaks, dico: Dict[str, np.ndarray]):
        "sets current bead peaks and computes the fits"
        dico['z'] = np.array([i for i, _ in peaks], dtype = 'f4')

class ReferencePeakInfo(PeakInfo):
    "All FitToReferenceTask related info"
    def keys(self, mdl: 'PeaksPlotModelAccess') -> List[str]:
        "returns the list of keys"
        return [] if mdl.identification.task else ['id', 'distance']

    def values(self, mdl: 'PeaksPlotModelAccess', peaks, dico: Dict[str, np.ndarray]):
        "sets current bead peaks and computes the fits"
        zvals  = np.array([i for i, _ in peaks], dtype = 'f4')
        ided   = mdl.fittoreference.identifiedpeaks(zvals)
        dico.update(id = ided, distance = zvals - ided)

class IdentificationPeakInfo(PeakInfo):
    "All FitToHairpinTask related info"
    @staticmethod
    def basekeys() -> List[str]:
        "base keys"
        return ['id', 'distance', 'bases', 'orient']

    def keys(self, mdl: 'PeaksPlotModelAccess') -> List[str]:
        "returns the list of keys"
        names = self.basekeys()
        return names + [''.join(i) for i in product(mdl.sequences(...), names)]

    def defaults(self, mdl: 'PeaksPlotModelAccess', peaks) -> Dict[str, np.ndarray]:
        dflt = super().defaults(mdl, peaks)
        for i in dflt:
            if i.endswith('orient'):
                dflt[i]  = np.full(len(dflt[i]), ' ', dtype = '<U1')
        return dflt

    def values(self, mdl: 'PeaksPlotModelAccess', peaks, dico: Dict[str, np.ndarray]):
        "sets current bead peaks and computes the fits"
        zvals = np.array([i[0] for i in peaks], dtype = 'f4')
        for key, hyb in mdl.hybridisations(...).items():
            dist = mdl.getfitparameters(key)
            tmp  = mdl.identification.attribute('match', key).pair(zvals, *dist)['key']
            good = tmp >= 0
            ori  = dict(hyb)

            dico[key+'bases']          = (zvals - dist[1])*dist[0]
            dico[key+'id']      [good] = tmp[good]
            dico[key+'distance'][good] = (tmp - dico[key+'bases'])[good]
            dico[key+'orient']  [good] = ['-+ '[ori.get(int(i+0.01), 2)]
                                          for i in dico[key+'id'][good]]

            if key == mdl.sequencekey:
                for i in self.basekeys():
                    dico[i] = dico[key+i]

class StatsPeakInfo(PeakInfo):
    "All stats related info"
    def keys(self, mdl: 'PeaksPlotModelAccess') -> List[str]:
        "returns the list of keys"
        return ['duration', 'sigma', 'count', 'skew']

    def values(self, mdl: 'PeaksPlotModelAccess', peaks, dico: Dict[str, np.ndarray]):
        "sets current bead peaks and computes the fits"
        if len(peaks) == 0:
            return

        task = cast(EventDetectionTask, mdl.eventdetection.task)
        prob = Probability(framerate   = getattr(mdl.track, 'framerate', 30.),
                           minduration = task.events.select.minduration)
        dur  = mdl.track.phase.duration(..., task.phase) # type: ignore
        for i, (_, evts) in enumerate(peaks):
            val                 = prob(evts, dur)
            dico['duration'][i] = val.averageduration
            dico['sigma'][i]    = prob.resolution(evts)
            dico['count'][i]    = min(100., val.hybridisationrate*100.)
            dico['skew'][i]     = np.nanmedian(prob.skew(evts))

def createpeaks(self: 'PeaksPlotModelAccess', peaks) -> Dict[str, np.ndarray]:
    "Creates the peaks data"
    classes = [ZPeakInfo(), ReferencePeakInfo(), IdentificationPeakInfo(), StatsPeakInfo()]
    dico    = {}
    for i in classes:
        dico.update(i.defaults(self, peaks))
    for i in classes:
        i.values(self, peaks, dico)
    return dico
