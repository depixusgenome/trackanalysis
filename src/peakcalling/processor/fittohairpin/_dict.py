#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Matching experimental peaks to hairpins: tasks and processors"
from   pathlib                     import Path
from   typing                      import (
    Dict, Sequence, Iterator, Tuple, Union, Optional, Any, cast
)

import numpy                       as     np

from   data.views                  import TaskView
from   peakfinding.peaksarray      import (
    Output as PeakFindingOutput, PeakListArray, PeaksArray
)
from   peakfinding.processor       import SingleStrandProcessor, BaselinePeakProcessor
from   taskmodel                       import Level
from   taskcontrol.processor.taskview  import TaskViewProcessor
from   utils                           import updatecopy, asobjarray, isint
from   ...tohairpin                    import (
    HairpinFitter, Distance, PeakMatching, Pivot
)
from   ._model                      import (
    FitToHairpinTask, FitBead, PeakEvents, PeakEventsTuple
)

_PEAKS = Tuple[np.ndarray, PeakListArray]

class FitToHairpinDict(TaskView[FitToHairpinTask, int]):  # pylint: disable=too-many-ancestors
    "iterator over peaks grouped by beads"
    level:     Level = FitToHairpinTask.level
    config:    FitToHairpinTask
    _resolved: Union[str, Path, Tuple[Union[str, Path],...]]

    def beadextension(self, ibead) -> Optional[float]:
        """
        Return the median bead extension (phase 3 - phase 1)
        """
        return getattr(self.data, 'beadextension', lambda *_: None)(ibead)

    def phaseposition(self, phase: int, ibead: int) -> Optional[float]:
        """
        Return the median position for a given phase
        """
        return getattr(self.data, 'phaseposition', lambda *_: None)(phase, ibead)

    def distances(
            self,
            key:      int,
            inp:      Optional[PeakListArray] = None,
            baseline: Optional[bool]          = None,
            strand:   Optional[bool]          = None,
    ) -> Dict[Optional[str], Distance]:
        "compute distances from peak data"
        if inp is None:
            inp = self.__topeaks(cast(PeakEvents, cast(dict, self.data)[key]))
        bead = inp['peaks']
        return {
            name: calc.optimize(bead)
            for name, calc in self.fits(key, inp, baseline, strand).items()
        }

    def fits(
            self,
            key:      int,
            inp:      Optional[PeakListArray] = None,
            baseline: Optional[bool]          = None,
            strand:   Optional[bool]          = None
    ) -> Dict[Optional[str], HairpinFitter]:
        "compute distances from peak data"
        if inp is None:
            inp = self.__topeaks(cast(PeakEvents, cast(dict, self.data)[key]))

        fits = {i: j for i, j in self.config.fit.items() if len(j.peaks)}
        cstr = self.config.constraints.get(key, None)
        hpin = None if cstr is None else fits.get(cast(str, cstr[0]), None)
        if cstr is not None:
            if hpin is not None:
                fits = {cast(str, cstr[0]): hpin}
            fits = {i: updatecopy(j, **cstr[1]) for i, j in fits.items()}

        # discard fits that have a hairpin size either too small or too big
        if hpin is None and self.config.pullphaseratio is not None:
            extent = self.beadextension(key)
            if extent is not None:
                extent *= self.config.pullphaseratio
                fits    = {i: j for i, j in fits.items() if j.withinrange(extent)}

        if any(i.hassinglestrand for i in fits.values()):
            strand = self.__singlestrand(key, inp) is not None if strand is None else strand

            if strand is True:
                # single-strand found: use it as a pivot
                fits.update((i, updatecopy(j, pivot = Pivot.top))
                            for i, j in fits.items() if j.hassinglestrand)
            elif strand is False:
                # single-strand found as missing: discard it from fit
                fits.update((i, updatecopy(j, peaks = j.peaks[:-1]))
                            for i, j in fits.items() if j.hassinglestrand)

        if baseline is False or self.__baseline(key, inp) is False:
            # baseline missing: don't use it as a pivot
            fits.update((i, updatecopy(j, pivot = Pivot.absolute))
                        for i, j in fits.items() if not j.hassinglestrand)

        return fits

    # pylint: disable=arguments-differ
    def compute(self, aitem: Union[int, PeakEventsTuple]) -> FitBead:
        "Action applied to the frame"
        if getattr(self, '_resolved', None) != getattr(self.track, 'path', None):
            self.config    = self.config.resolve(self.track.path)
            self._resolved = self.track.path

        if isint(aitem):
            bead = cast(int, aitem)
            inp  = cast(PeakEvents, cast(dict, self.data)[bead])
        else:
            bead, inp = cast(PeakEventsTuple, aitem)

        events       = self.__topeaks(inp)
        baseline     = self.__baseline(bead, inp)
        singlestrand = self.__singlestrand(bead, inp)
        dist         = self.distances(
            bead,
            events,
            baseline     is not None,
            singlestrand is not None
        )
        return self.__beadoutput(bead, events, dist, (baseline, singlestrand))

    @classmethod
    def _transform_ids(cls, sel):
        return cls._transform_to_bead_ids(sel)

    @staticmethod
    def __topeaks(aevts:PeakEvents) -> PeakListArray:
        "converts PeakEvents to PeakListArray"
        if not isinstance(aevts, Iterator):
            evts = cast(Sequence[PeakFindingOutput], aevts)
            if getattr(evts, 'dtype', 'O') == 'f4':
                return PeakListArray([(i, PeaksArray([])) for i in evts])
        else:
            evts = tuple(aevts)

        disc = (getattr(evts, 'discarded', 0) if hasattr(evts, 'discarded') else
                0                             if len(evts) == 0             else
                getattr(evts[0][1], 'discarded', 0))
        evts = asobjarray(((i, asobjarray(j)) for i, j in evts),
                          view      = PeakListArray,
                          discarded = disc).astype(getattr(PeakListArray, '_dtype'))
        return cast(PeakListArray, evts)

    def __baseline(self, bead:int, peaks: PeakListArray) -> Optional[float]:
        out = (
            BaselinePeakProcessor(task = self.config.baseline)
            .index(self.data, bead, peaks)
        )
        return None if out is None else peaks[out][0]

    def __singlestrand(self, bead:int, peaks: PeakListArray) -> Optional[float]:
        out = (
            SingleStrandProcessor(task = self.config.singlestrand)
            .index(self.data, bead, peaks)
        )
        return None if out is None or out >= len(peaks) else peaks[out][0]

    def __beadoutput(
            self,
            key:    int,
            events: PeakListArray,
            dist:   Dict[Optional[str], Distance],
            refs:   Tuple[Optional[float], Optional[float]]
    ) -> FitBead:
        if len(dist) == 0:
            return FitBead(
                key, -1., dist, PeakMatching.empty(events['peaks']), events, *refs
            )

        best = cast(str, min(dist, key = dist.__getitem__))
        silh = HairpinFitter.silhouette(dist, best)
        alg  = self.config.match.get(best, self.config.DEFAULT_MATCH())
        ids  = alg.pair(events['peaks'], *dist.get(best, (0., 1., 0))[1:])
        return FitBead(key, silh, dist, ids, events, *refs)

class FitToHairpinProcessor(TaskViewProcessor[FitToHairpinTask, FitToHairpinDict, int]):
    "Groups beads per hairpin"
    @staticmethod
    def keywords(cnf:Dict[str, Any]) -> Dict[str, Any]:
        "changes keywords as needed"
        fit         = cnf.get('fit',         None)
        match       = cnf.get('match',       None)
        constraints = cnf.get('constraints', None)
        cnf.update(fit         = {} if not fit         else fit,  # type: ignore
                   constraints = {} if not constraints else constraints,
                   match       = {} if not match       else match)
        return cnf
