#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Creating a dictionnary with all peak related stuff"
from typing                     import Dict, List, TYPE_CHECKING, cast
from abc                        import ABC, abstractmethod
from itertools                  import product
from eventdetection.processor   import EventDetectionTask
from peakcalling.processor      import FitToHairpinTask

import numpy                    as     np

from peakfinding.probabilities  import Probability

if TYPE_CHECKING:
    from ._model                import PeaksPlotModelAccess # pylint: disable=unused-import

class PeakInfo(ABC):
    "Creates a peaks info dictionnary"
    @abstractmethod
    def keys(self, mdl: 'PeaksPlotModelAccess') -> List[str]:
        "returns the list of keys"

    @abstractmethod
    def values(self, mdl: 'PeaksPlotModelAccess', peaks) -> Dict[str, np.ndarray]:
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
    def values(mdl: 'PeaksPlotModelAccess', peaks):
        "sets current bead peaks and computes the fits"
        return {'z': np.array([i for i, _ in peaks], dtype = 'f4')}

class ReferencePeakInfo(PeakInfo):
    "All FitToReferenceTask related info"
    def keys(self, mdl: 'PeaksPlotModelAccess') -> List[str]:
        "returns the list of keys"
        return [] if mdl.identification.task else ['id', 'distance']

    def values(self, mdl: 'PeaksPlotModelAccess', peaks) -> Dict[str, np.ndarray]:
        "sets current bead peaks and computes the fits"
        zvals  = np.array([i for i, _ in peaks], dtype = 'f4')
        ided   = mdl.fittoreference.identifiedpeaks(zvals)
        return dict(id = ided, distance = zvals - ided)

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

    def values(self, mdl: 'PeaksPlotModelAccess', peaks) -> Dict[str, np.ndarray]:
        "sets current bead peaks and computes the fits"
        zvals = np.array([i for i, _ in peaks], dtype = 'f4')
        if not len(mdl.distances):
            return {'bases': (zvals-mdl.bias)*mdl.stretch}

        strori  = mdl.css.stats.title.orientation.get()
        alldist = mdl.distances
        dico    = {}
        task    = cast(FitToHairpinTask, mdl.identification.task)
        for key, hyb in mdl.hybridisations(...).items():
            if key not in alldist: # type: ignore
                continue

            dist = alldist[key].stretch, alldist[key].bias
            tmp  = task.match[key].pair(zvals, *dist)['key'] # type: ignore
            good = tmp >= 0
            ori  = dict(hyb)

            dico[f'{key}bases'] = (zvals - dist[1])*dist[0]

            dico.update({f'{key}{i}': np.full(len(zvals), np.NaN, dtype = 'f4')
                         for i in ('id', 'distance')})

            dico[f'{key}id']      [good] = tmp[good]
            dico[f'{key}distance'][good] = (tmp - dico[f'{key}bases'])[good]
            dico[f'{key}orient']         = np.full(len(zvals), ' ', dtype = '<U1')
            dico[f'{key}orient']  [good] = [strori[ori.get(int(i+0.01), 2)]
                                            for i in dico[f'{key}id'][good]]

        if mdl.sequencekey in mdl.distances:
            for i in self.basekeys():
                dico[i] = dico[mdl.sequencekey+i]
        return dico

class StatsPeakInfo(PeakInfo):
    "All stats related info"
    def keys(self, mdl: 'PeaksPlotModelAccess') -> List[str]:
        "returns the list of keys"
        return ['duration', 'sigma', 'count', 'skew']

    def values(self, mdl: 'PeaksPlotModelAccess', peaks) -> Dict[str, np.ndarray]:
        "sets current bead peaks and computes the fits"
        if len(peaks) == 0:
            return {}

        task = cast(EventDetectionTask, mdl.eventdetection.task)
        prob = Probability(framerate   = mdl.track.framerate,
                           minduration = task.events.select.minduration)
        dur  = mdl.track.phase.duration(..., task.phase) # type: ignore
        dico = self.defaults(mdl, peaks)
        for i, (_, evts) in enumerate(peaks):
            val                 = prob(evts, dur)
            dico['duration'][i] = val.averageduration
            dico['sigma'][i]    = prob.resolution(evts)
            dico['count'][i]    = min(100., val.hybridisationrate*100.)
            dico['skew'][i]     = np.nanmedian(prob.skew(evts))
        return dico

def createpeaks(self: 'PeaksPlotModelAccess', peaks) -> Dict[str, np.ndarray]:
    "Creates the peaks data"
    classes = [ZPeakInfo(), ReferencePeakInfo(), IdentificationPeakInfo(), StatsPeakInfo()]
    dico    = {}
    for i in classes:
        dico.update(i.defaults(self, peaks))
    for i in classes:
        dico.update(i.values  (self, peaks))
    return dico
