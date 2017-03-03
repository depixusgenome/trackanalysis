#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Matching experimental peaks to hairpins: tasks and processors"
from   typing       import (Dict, Sequence, NamedTuple,
                            Iterator, Tuple, Union, Iterable, Optional)
from   functools    import partial
import numpy        as np

from utils                  import StreamUnion, initdefaults, updatecopy, asobjarray
from data.trackitems        import BEADKEY, TrackItems
from peakfinding.selector   import Output as PeakFindingOutput
from peakfinding.processor  import PeaksDict
from model                  import Task, Level
from control.processor      import Processor
from .tohairpin             import (HairpinDistance, Distance,
                                    PeakIdentifier, PEAKS_TYPE)

DistanceConstraint = NamedTuple('DistanceConstraint',
                                [('hairpin', str), ('constraints', dict)])

Distances   = Dict[str,     HairpinDistance]
Constraints = Dict[BEADKEY, DistanceConstraint]
PeakIds     = Dict[str,     PeakIdentifier]

class FitToHairpinTask(Task):
    u"Fits a bead to all hairpins"
    level       = Level.peak
    distances   = dict() # type: Distances
    constraints = dict() # type: Constraints
    peakids     = dict() # type: PeakIds
    @initdefaults
    def __init__(self, **_):
        super().__init__()

    @classmethod
    def read(cls, path : StreamUnion, oligos : Sequence[str]) -> 'BeadsByHairpinTask':
        u"creates a BeadsByHairpin from a fasta file and a list of oligos"
        items = dict(HairpinDistance.read(path, oligos))
        return cls(distances = items,
                   peakids   = {key: PeakIdentifier(peaks = value.peaks)
                                for key, value in items.items()})

class BeadsByHairpinTask(FitToHairpinTask):
    u"Groups beads per hairpin"
    level       = Level.peak
    distances   = dict() # type: Distances
    constraints = dict() # type: Constraints
    peakids     = dict() # type: PeakIds
    @initdefaults
    def __init__(self, **_):
        super().__init__()

    @classmethod
    def read(cls, path : StreamUnion, oligos : Sequence[str]) -> 'BeadsByHairpinTask':
        u"creates a BeadsByHairpin from a fasta file and a list of oligos"
        items = dict(HairpinDistance.read(path, oligos))
        return cls(distances = items,
                   peakids   = {key: PeakIdentifier(peaks = value.peaks)
                                for key, value in items.items()})

Input  = Union[PeaksDict, Iterable[Tuple[BEADKEY,np.ndarray]]]
_PEAKS = Tuple[Sequence[float], Sequence[PeakFindingOutput]]


FitBead  = NamedTuple('FitBead',
                      [('key',         BEADKEY),
                       ('silhouette',  float),
                       ('distances',   Dict[Optional[str],Distance]),
                       ('peaks',       PEAKS_TYPE),
                       ('events',      PeakFindingOutput)])

class FitToHairpinProcessor(Processor):
    u"Groups beads per hairpin"
    @Processor.action
    def run(self, _):
        cnf  = self.config()
        vals = cnf['distances'], cnf['constrainst'], cnf['peakids']
        return partial(self.apply, *vals)

    @classmethod
    def apply(cls,
              distances     : Distances,
              constraints   : Constraints,
              peakids       : PeakIds,
              item          : Tuple[BEADKEY,Sequence[PeakFindingOutput]]
             ) -> Tuple[BEADKEY,FitBead]:
        u"Action applied to the frame"
        peaks, events = cls.__topeaks(item[1])
        dist          = cls.__distances(distances, constraints, item[0], peaks)
        out           = cls.__beadoutput(peakids, item[0], peaks, events, dist)
        return out.key, out

    @classmethod
    def __topeaks(cls, evts:Sequence[PeakFindingOutput]) -> _PEAKS:
        u"Regroups the beads from a frame by hairpin"
        if isinstance(evts, Iterator):
            evts = tuple(evts)

        if len(evts) == 0:
            return np.empty((0,), dtype = 'f4'), np.empty((0,), dtype = 'O')

        if getattr(evts, 'dtype', 'O') == 'f4':
            return evts, np.empty((0,), dtype = 'O')
        else:
            evts = asobjarray((i, asobjarray(j)) for i, j in evts)
            return (np.array([i for i, _ in evts], dtype = 'f4'), evts)

    @staticmethod
    def __distances(distances   : Distances,
                    constraints : Constraints,
                    key         : str,
                    bead        : Sequence[float])->Dict[Optional[str], Distance]:
        cstr = constraints.get(key, None)
        if cstr is not None:
            hpin = distances.get(cstr[0], None)
            if hpin is not None:
                return {cstr[0]: updatecopy(hpin, **cstr[1])(bead)}

        if len(bead) > 0:
            return {name: calc(bead) for name, calc in distances.items()}

        else:
            return {None: next(iter(distances.values()))(bead)}

    @staticmethod
    def __beadoutput(peakids : PeakIds,
                     key     : BEADKEY,
                     peaks   : Sequence[float],
                     events  : Sequence[PeakFindingOutput],
                     dist    : Dict[Optional[str], Distance],
                    ) -> FitBead:
        best  = min(dist, key = dist.__getitem__)
        if len(dist) > 1:
            aval = dist[best].value
            bval = min(i[0] for k, i in dist.items() if k != best)
            silh = ((bval-aval)/max(aval, bval)-.5)*2.
        else:
            silh = 1. if len(dist) == 1 else -3.

        alg = peakids.get(best, PeakIdentifier())
        ids = alg(peaks, *dist.get(best, (0., 1., 0))[1:])
        return FitBead(key, silh, dist, ids, events)

ByHairpinBead  = NamedTuple('ByHairpinBead',
                            [('key',         BEADKEY),
                             ('silhouette',  float),
                             ('distance',    Distance),
                             ('peaks',       PEAKS_TYPE),
                             ('events',      PeakFindingOutput)])
ByHairpinGroup = NamedTuple('ByHairpinGroup',
                            [('key', str), ('beads', Sequence[ByHairpinBead])])

class BeadsByHairpinProcessor(Processor):
    u"Groups beads per hairpin"
    @classmethod
    def apply(cls,
              dist  : Distances,
              cstr  : Constraints,
              ids   : PeakIds,
              frame : Input,
             ) -> Iterator[ByHairpinGroup]:
        u"Regroups the beads from a frame by hairpin"
        fcn  = FitToHairpinProcessor.apply
        out  = dict(fcn(dist, cstr, ids, i) for i in frame) # type: Dict[BEADKEY,FitBead]
        best = {itm.key: min(itm.distances, key = itm.distances.__getitem__)
                for itm in out.values()}
        for hpname in sorted(set(best.values()), key = lambda x: x or chr(255)):
            vals = (cls.__out(val, hpname)
                    for key, val in out.items()
                    if best[key] == hpname)
            yield ByHairpinGroup(hpname,
                                 sorted(vals,
                                        key     = lambda i: i.silhouette,
                                        reverse = True))

    def run(self, args):
        cnf = self.config()
        app = self.apply
        def _run(frame):
            def _lazy():
                return {i.key: i for i in app(cnf['distances'],
                                              cnf['constraints'],
                                              cnf['peakids'],
                                              frame)}

            return TrackItems(track = frame.track, data = _lazy)
        args.apply(_run)

    @classmethod
    def __out(cls, bead: FitBead, hpname:str) -> ByHairpinBead:
        return ByHairpinBead(*bead[:2], bead[2][hpname], *bead[3:])
