#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Creating a dictionnary with all peak related stuff"
from typing                     import Dict, List, Optional, TYPE_CHECKING, cast
from abc                        import ABC, abstractmethod
from itertools                  import product

import numpy                    as     np

from eventdetection.processor   import EventDetectionTask
from peakfinding.peaksarray     import PeakListArray
from peakfinding.probabilities  import Probability
from sequences                  import markedoligos
from utils                      import NoArgs

if TYPE_CHECKING:
    from ._model                import PeaksPlotModelAccess # pylint: disable=unused-import

class PeakInfoModelAccess:
    "wrapper to acces model info"
    def __init__(self, mdl, bead = NoArgs, classes = NoArgs):
        self._model   = mdl
        self._bead    = bead
        self._classes = classes

    def oligos(self) -> List[str]:
        "return the search window for unknown peaks"
        return self._model.oligos

    def hasidentification(self) -> bool:
        "whether the model has an FitToHairpinTask"
        return self._model.identification.task is not None

    def identifiedpeaks(self, zvals):
        "the identified peaks"
        return self._model.fittoreference.identifiedpeaks(zvals, self._bead)

    def sequences(self):
        "return the sequences available"
        return self._model.sequences(...)

    def getfitparameters(self, key):
        "return fit parameters"
        return self._model.getfitparameters(key, self._bead)

    def hybridisations(self):
        "return hybridizations"
        return self._model.hybridisations(...)

    def matchpairs(self, key, zvals):
        "return matched pairs"
        dist = self.getfitparameters(key)
        return self._model.identification.attribute('match', key).pair(zvals, *dist)['key']

    @property
    def sequencekey(self):
        "return the current sequence"
        return self._model.sequencekey

    @property
    def track(self):
        "return the current track"
        return self._model.track

    @property
    def eventdetectiontask(self):
        "return the current track"
        return self._model.eventdetection.task

    def createpeaks(self, peaks: PeakListArray) -> Dict[str, np.ndarray]:
        "Creates the peaks data"
        dico: Dict[str, np.ndarray] = {}
        classes                     = self._classes
        if classes is NoArgs:
            classes = [
                ZPeakInfo(),                ReferencePeakInfo(),
                IdentificationPeakInfo(),   StatsPeakInfo()
            ]

        for i in classes:
            dico.update(i.defaults(self, peaks))
        for i in classes:
            i.values(self, peaks, dico)
        return dico

class PeakInfo(ABC):
    "Creates a peaks info dictionnary"
    @abstractmethod
    def keys(self, mdl: PeakInfoModelAccess) -> List[str]:
        "returns the list of keys"

    @abstractmethod
    def values(
            self,
            mdl:   PeakInfoModelAccess,
            peaks: PeakListArray,
            dico:  Dict[str, np.ndarray]
    ):
        "sets current bead peaks and computes the fits"

    def defaults(
            self,
            mdl:   PeakInfoModelAccess,
            peaks: PeakListArray
    ) -> Dict[str, np.ndarray]:
        "sets current bead peaks and computes the fits"
        size = len(peaks)
        return {i: np.full(size, np.NaN, dtype = 'f4') for i in self.keys(mdl)}

class ZPeakInfo(PeakInfo):
    "All base peak-related info"
    @staticmethod
    def keys(mdl: PeakInfoModelAccess) -> List[str]:
        "returns the list of keys"
        return ['z']

    @staticmethod
    def values(
            mdl:   PeakInfoModelAccess,
            peaks: PeakListArray,
            dico:  Dict[str, np.ndarray]
    ):
        "sets current bead peaks and computes the fits"
        dico['z'] = np.array([i for i, _ in peaks], dtype = 'f4')

class ReferencePeakInfo(PeakInfo):
    "All FitToReferenceTask related info"
    def keys(self, mdl: PeakInfoModelAccess) -> List[str]:
        "returns the list of keys"
        return [] if mdl.hasidentification else ['id', 'distance']

    def values(
            self,
            mdl:   PeakInfoModelAccess,
            peaks: PeakListArray,
            dico:  Dict[str, np.ndarray]
    ):
        "sets current bead peaks and computes the fits"
        zvals  = np.array([i for i, _ in peaks], dtype = 'f4')
        ided   = mdl.identifiedpeaks(zvals)
        dico.update(id = ided, distance = zvals - ided)

class IdentificationPeakInfo(PeakInfo):
    "All FitToHairpinTask related info"
    @staticmethod
    def basekeys() -> List[str]:
        "base keys"
        return ['id', 'distance', 'bases', 'orient']

    def keys(self, mdl: PeakInfoModelAccess) -> List[str]:
        "returns the list of keys"
        names = self.basekeys()
        return names + [''.join(i) for i in product(mdl.sequences(), names)]

    def defaults(self, mdl: PeakInfoModelAccess, peaks: PeakListArray) -> Dict[str, np.ndarray]:
        dflt = super().defaults(mdl, peaks)
        for i in dflt:
            if i.endswith('orient'):
                dflt[i] = self.defaultstrand(mdl, peaks)
        return dflt

    @classmethod
    def defaultstrand(
            cls,
            mdl: PeakInfoModelAccess,
            peaks: PeakListArray
    ) -> np.ndarray:
        "return the empty strand array"
        return cls.strand(mdl, None, None, peaks, np.empty([]))

    @staticmethod
    def strand(
            mdl:   PeakInfoModelAccess,
            seq:   Optional[str],
            hyb:   Optional[np.ndarray],
            ids:   np.ndarray,
            bases: np.ndarray
    ) -> np.ndarray:
        "return the strand array"
        oligs = markedoligos(mdl.oligos())
        neigh = 2
        win   = max((len(i)+2*neigh for i in oligs), default = 0)
        arr   = np.full(len(ids), ' ', dtype = f'<U{win+1}')
        if seq is None:
            return arr

        def _set(ind):
            info = seq[max(ind-win+neigh, 0):ind+2+neigh].lower()
            for i, j in oligs.items():
                info = info.replace(i, j)
            return info

        good       = np.isfinite(ids)
        ori        = dict(hyb if hyb is not None else ())
        arr[good]  = [
            '\u2796\u2795 '[int(ori.get(int(i+0.01), 2))]+" "+_set(i)
            for i in ids[good].astype('i4')
        ]
        arr[~good] = ['  '+_set(i) for i in bases[~good].astype("i4")]

        return arr

    def values(
            self,
            mdl:   PeakInfoModelAccess,
            peaks: PeakListArray,
            dico:  Dict[str, np.ndarray]
    ):
        "sets current bead peaks and computes the fits"
        zvals         = np.array([i[0] for i in peaks], dtype = 'f4')
        dist          = mdl.getfitparameters(mdl.sequencekey)
        dico['bases'] = (zvals - dist[1])*dist[0]
        seqs          = mdl.sequences()
        for key, hyb in mdl.hybridisations().items():
            dist = mdl.getfitparameters(key)
            tmp  = mdl.matchpairs(key, zvals)
            good = tmp >= 0

            dico[key+'bases']          = ((zvals - dist[1])*dist[0])
            dico[key+'id']      [good] = tmp[good]
            dico[key+'distance'][good] = (tmp - dico[key+'bases'])[good]
            dico[key+'orient']         = self.strand(
                mdl, seqs[key], hyb, dico[key+'id'], dico[key+'bases']
            )
            if key == mdl.sequencekey:
                for i in self.basekeys():
                    dico[i] = dico[key+i]

class StatsPeakInfo(PeakInfo):
    "All stats related info"
    def keys(self, mdl: PeakInfoModelAccess) -> List[str]:
        "returns the list of keys"
        return ['duration', 'sigma', 'count', 'skew']

    def values(
            self,
            mdl:   PeakInfoModelAccess,
            peaks: PeakListArray,
            dico:  Dict[str, np.ndarray]
    ):
        "sets current bead peaks and computes the fits"
        if len(peaks) == 0:
            return

        track = mdl.track
        task  = cast(EventDetectionTask, mdl.eventdetectiontask)
        prob  = Probability(framerate   = getattr(track, 'framerate', 30.),
                            minduration = task.events.select.minduration)
        dur   = track.phase.duration(..., task.phase) # type: ignore
        for i, (_, evts) in enumerate(peaks):
            val                 = prob(evts, dur)
            dico['duration'][i] = val.averageduration
            dico['sigma'][i]    = prob.resolution(evts)
            dico['count'][i]    = min(100., val.hybridisationrate*100.)
            dico['skew'][i]     = np.nanmedian(prob.skew(evts))

def createpeaks(self, peaks: PeakListArray) -> Dict[str, np.ndarray]:
    "Creates the peaks data"
    if not isinstance(self, PeakInfoModelAccess):
        return PeakInfoModelAccess(self).createpeaks(peaks)
    return self.createpeaks(peaks)
