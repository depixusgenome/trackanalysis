#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Matching experimental peaks to hairpins: tasks and processors"
from   typing                      import (Dict, # pylint: disable=unused-import
                                           List, Sequence, NamedTuple, FrozenSet,
                                           Type, Iterator, Tuple, Union, Optional,
                                           Iterable, Any, cast)
from   copy                        import deepcopy

import numpy                       as     np

from   utils                       import (StreamUnion, initdefaults, updatecopy,
                                           asobjarray, DefaultValue)
from   model                       import Task, Level
from   control.processor.taskview  import TaskViewProcessor
from   control.processor.dataframe import DataFrameFactory
from   data.views                  import BEADKEY, Beads, TaskView
from   peakfinding.selector        import Output as PeakFindingOutput, PeaksArray
from   peakfinding.processor       import PeaksDict
from   ..tohairpin                 import (HairpinFitter, PeakGridFit, Distance,
                                           PeakMatching, PEAKS_TYPE)

class DistanceConstraint(NamedTuple): # pylint: disable=missing-docstring
    hairpin     : str
    constraints : dict

Fitters     = Dict[str,     HairpinFitter]
Constraints = Dict[BEADKEY, DistanceConstraint]
Matchers    = Dict[str,     PeakMatching]

class FitToHairpinTask(Task):
    "Fits a bead to all hairpins"
    level                     = Level.peak
    fit         : Fitters     = dict()
    constraints : Constraints = dict()
    match       : Matchers    = dict()
    DEFAULT_FIT               = PeakGridFit
    DEFAULT_MATCH             = PeakMatching

    def __delayed_init__(self, kwa):
        if not isinstance(self.fit, dict):
            self.fit = {}
        if not isinstance(self.match, dict):
            self.match = {}

        if 'sequence' in kwa:
            other = self.read(kwa['sequence'], kwa['oligos'],
                              fit   = kwa.get('fit',   None),
                              match = kwa.get('match', None))
            self.fit.update(other.fit)
            self.match.update(other.match)

    @initdefaults(frozenset(locals()) - {'level'})
    def __init__(self, **kwa):
        super().__init__(**kwa)

    def __scripting__(self, kwa):
        self.__delayed_init__(kwa)
        return self

    @classmethod
    def isslow(cls) -> bool:
        "whether this task implies long computations"
        return True

    @classmethod
    def read(cls,
             path   : StreamUnion,
             oligos : Sequence[str],
             fit    : Type[HairpinFitter] = None,
             match  : Type[PeakMatching]  = None
            ) -> 'FitToHairpinTask':
        "creates a BeadsByHairpin from a fasta file and a list of oligos"
        if fit is None or fit is DefaultValue:
            fits = dict(cls.DEFAULT_FIT.read(path, oligos))
        elif isinstance(fit, type):
            fits = dict(cast(Type[HairpinFitter], fit).read(path, oligos))
        else:
            ifit = cast(HairpinFitter, fit)
            fits = {i: updatecopy(ifit, True, peaks = j.peaks)
                    for i, j in ifit.read(path, oligos)}

        imatch = (cls.DEFAULT_MATCH() if match in (None, DefaultValue) else
                  cast(Type[PeakMatching], match)() if isinstance(match, type) else
                  cast(PeakMatching, match))

        return cls(fit   = fits,
                   match = {key: updatecopy(imatch, True, peaks = value.peaks)
                            for key, value in fits.items()})

PeakEvents      = Iterable[PeakFindingOutput]
PeakEventsTuple = Tuple[BEADKEY, PeakEvents]
_PEAKS          = Tuple[np.ndarray, PeaksArray]
Input           = Union[PeaksDict, PeakEvents]
class FitBead(NamedTuple): # pylint: disable=missing-docstring
    key        : BEADKEY
    silhouette : float
    distances  : Dict[Optional[str], Distance]
    peaks      : PEAKS_TYPE
    events     : PeakEvents

class FitToHairpinDict(TaskView[FitToHairpinTask, BEADKEY]):
    "iterator over peaks grouped by beads"
    level  = Level.bead
    @staticmethod
    def __topeaks(aevts:PeakEvents) -> _PEAKS:
        "Regroups the beads from a frame by hairpin"
        if not isinstance(aevts, Iterator):
            evts = cast(Sequence[PeakFindingOutput], aevts)
            if getattr(evts, 'dtype', 'O') == 'f4':
                return cast(np.ndarray, evts), PeaksArray([], dtype = 'O')
        else:
            evts = tuple(aevts)

        disc = (getattr(evts, 'discarded', 0) if hasattr(evts, 'discarded') else
                0                             if len(evts) == 0             else
                getattr(evts[0][1], 'discarded', 0))
        evts = asobjarray(((i, asobjarray(j)) for i, j in evts),
                          view      = PeaksArray,
                          discarded = disc)
        return np.array([i for i, _ in evts], dtype = 'f4'), cast(PeaksArray, evts)

    def __distances(self, key: BEADKEY, bead: Sequence[float])->Dict[Optional[str], Distance]:
        fits        = self.config.fit
        constraints = self.config.constraints
        cstr        = constraints.get(key, None)
        if cstr is not None:
            hpin = fits.get(cstr[0], None)
            if hpin is not None:
                return {cstr[0]: updatecopy(hpin, **cstr[1]).optimize(bead)}

        if len(bead) > 0:
            return {name: calc.optimize(bead) for name, calc in fits.items()}

        return {None: next(iter(fits.values())).optimize(bead)}

    def __beadoutput(self,
                     key     : BEADKEY,
                     peaks   : Sequence[float],
                     events  : PeakEvents,
                     dist    : Dict[Optional[str], Distance],
                    ) -> FitBead:
        best = min(dist, key = dist.__getitem__)
        silh = HairpinFitter.silhouette(dist, best)
        alg  = self.config.match.get(best, self.config.DEFAULT_MATCH())
        ids  = alg.pair(peaks, *dist.get(best, (0., 1., 0))[1:])
        return FitBead(key, silh, dist, ids, events)

    def compute(self, aitem: Union[BEADKEY, PeakEventsTuple]) -> FitBead:
        "Action applied to the frame"
        if Beads.isbead(aitem):
            bead = cast(BEADKEY, aitem)
            inp  = cast(PeakEvents,  self.data[bead])
        else:
            bead, inp = cast(PeakEventsTuple, aitem)


        peaks, events = self.__topeaks(inp)
        dist          = self.__distances(bead, peaks)
        return self.__beadoutput(bead, peaks, events, dist)

class FitToHairpinProcessor(TaskViewProcessor[FitToHairpinTask, FitToHairpinDict, BEADKEY]):
    "Groups beads per hairpin"
    @staticmethod
    def keywords(cnf:Dict[str, Any]) -> Dict[str, Any]:
        "changes keywords as needed"
        fit         = cnf.get('fit',         None)
        match       = cnf.get('match',       None)
        constraints = cnf.get('constraints', None)
        cnf.update(fit         = {} if not fit         else fit, # type: ignore
                   constraints = {} if not constraints else constraints,
                   match       = {} if not match       else match)
        return cnf

class FitsDataFrameFactory(DataFrameFactory[FitToHairpinDict]):
    "converts to a pandas dataframe."
    # pylint: disable=arguments-differ
    @staticmethod
    def _run(_1, _2, res:FitBead) -> Dict[str, np.ndarray]: # type: ignore
        out = {i: [] for i in ('cycle', 'peak', 'event')}   # type: Dict[str, List[np.ndarray]]
        out.update({i: [] for i in res.distances})
        for (peak, evts) in PeaksDict.measure(cast(PeaksArray, deepcopy(res.events))):
            vals = [i for i in enumerate(evts) if i[1] is not None]

            out['cycle'].append(np.array([i for i, _ in vals]))
            out['peak'].append(np.full(len(vals), peak, dtype = 'f4'))
            out['event'].append(np.array([i for _, i in vals]))
            for i, j in res.distances.items():
                out[i].append((out['event'][-1]-j.bias)*j.stretch)
        return {i: np.concatenate(j) for i, j in out.items()}
