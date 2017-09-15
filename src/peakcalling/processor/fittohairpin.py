#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Matching experimental peaks to hairpins: tasks and processors"
from   typing       import (Dict, Sequence, NamedTuple, FrozenSet, Type,
                            Iterator, Tuple, Union, Optional, Iterable, cast)
import numpy        as     np

from utils                      import StreamUnion, initdefaults, updatecopy, asobjarray
from model                      import Task, Level
from control.processor          import Processor
from data.views                 import BEADKEY, TrackView, Beads
from peakfinding.selector       import Output as PeakFindingOutput, PeaksArray
from peakfinding.processor      import PeaksDict
from ..tohairpin                import (HairpinFitter, GaussianProductFit, Distance,
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
    @initdefaults(frozenset(locals()) - {'level'})
    def __init__(self, **kwa):
        super().__init__()
        if 'sequence' in kwa:
            assert 'oligo' in kwa
            self.__init_sequence(kwa)

    def __init_sequence(self, kwa):
        if 'sequence' in kwa:
            other = self.read(kwa['sequence'], kwa['oligos'],
                              fit   = kwa.get('fit',   None),
                              match = kwa.get('match', None))
            self.fit.update(other.fit)
            self.match.update(other.match)

    def __scripting__(self, kwa):
        self.__init_sequence(kwa)
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
        if fit is None:
            fits = dict(GaussianProductFit.read(path, oligos))
        elif isinstance(fit, type):
            fits = dict(cast(Type[HairpinFitter], fit).read(path, oligos))
        else:
            ifit = cast(HairpinFitter, fit)
            fits = {i: updatecopy(ifit, True, peaks = j.peaks)
                    for i, j in ifit.read(path, oligos)}

        imatch = (PeakMatching()                    if match is None           else
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

class FitToHairpinDict(TrackView):
    "iterator over peaks grouped by beads"
    level = Level.bead
    def __init__(self, *_, config = None, **kwa):
        assert len(_) == 0
        super().__init__(**kwa)
        if config is None:
            self.config = FitToHairpinTask()
        elif isinstance(config, dict):
            self.config = FitToHairpinTask(**config)
        else:
            assert isinstance(config, FitToHairpinTask), config
            self.config = config
        self.__keys: FrozenSet[BEADKEY] = None

    def _keys(self, sel:Sequence = None, _ = None) -> Iterator[BEADKEY]:
        if self.__keys is None:
            self.__keys = frozenset(self.data.keys())

        if sel is None:
            yield from self.__keys
        else:
            yield from (i for i in self.__keys if i in sel)

    def _iter(self, sel:Sequence = None) -> Iterator[Tuple[BEADKEY, FitBead]]:
        if isinstance(self.data, FitToHairpinDict):
            itr = iter(cast(Iterable, self.data))
            if sel is None:
                yield from itr
            else:
                yield from ((i, j) for i, j in itr if i in sel)
        yield from ((bead, self.compute(bead)) for bead in self.keys(sel))

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
        alg  = self.config.match.get(best, PeakMatching())
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

class FitToHairpinProcessor(Processor):
    "Groups beads per hairpin"
    @classmethod
    def apply(cls, toframe = None, **cnf):
        "applies the task to a frame or returns a function that does so"
        fcn = lambda frame: frame.new(FitToHairpinDict, config = cnf)
        return fcn if toframe is None else fcn(toframe)

    @classmethod
    def compute(cls,
                item        : Union[BEADKEY, PeakEventsTuple],
                fit         : Fitters     = None,
                constraints : Constraints = None,
                match       : Matchers    = None,
                **cnf
               ) -> Tuple[BEADKEY,FitBead]:
        "Action applied to the frame"
        cnf.update(fit         = {} if fit         is None else fit, # type: ignore
                   constraints = {} if constraints is None else constraints,
                   match       = {} if match       is None else match)
        out = FitToHairpinDict(config = cnf).compute(item)
        return out.key, out

    def run(self, args):
        args.apply(self.apply(**self.config()))
