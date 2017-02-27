#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Matching experimental peaks to hairpins: tasks and processors"
from   typing       import (Dict, Sequence, NamedTuple, # pylint: disable=unused-import
                            Iterator, Tuple, Union, Any, Iterable, cast)
from   functools    import partial
import numpy        as np

from utils                  import StreamUnion, initdefaults, updatecopy
from data.trackitems        import BEADKEY
from peakfinding.selector   import Output as PeakFindingOutput
from model                  import Task, Level
from control.processor      import Processor
from .tohairpin             import (HairpinDistance, Distance,
                                    PeakIdentifier, PEAKS_TYPE)

DistanceConstraint = NamedTuple('DistanceConstraint',
                                [('hairpin', str), ('constraints', dict)])

Distances   = Dict[str,     HairpinDistance]
Constraints = Dict[BEADKEY, DistanceConstraint]
PeakIds     = Dict[str,     PeakIdentifier]

class BeadsByHairpinTask(Task):
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
        return cls(hairpins = items,
                   peakids  = {key: PeakIdentifier(**value.config())
                               for key, value in items.items()})

ByHairpinBead  = NamedTuple('ByHairpinBead',
                            [('key',        BEADKEY),
                             ('silhouette', float),
                             ('distance',   Distance),
                             ('peaks',      PEAKS_TYPE),
                             ('events',     PeakFindingOutput)])

ByHairpinGroup = NamedTuple('ByHairpinGroup',
                            [('key',       str),
                             ('beads',     Sequence[ByHairpinBead])])


Input  = Tuple[BEADKEY, Iterable[PeakFindingOutput]]
_PEAKS = Dict[BEADKEY, Tuple[Sequence[float], Sequence[PeakFindingOutput]]]
class BeadsByHairpinProcessor(Processor):
    u"Groups beads per hairpin"
    tasktype = BeadsByHairpinTask

    @classmethod
    def apply(cls,
              distances     : Distances,
              constraints   : Constraints,
              peakids       : PeakIds,
              frame         : Iterable[Tuple[BEADKEY, Iterable[Input]]]
             ) -> Iterator[ByHairpinGroup]:
        u"Regroups the beads from a frame by hairpin"
        peaks = cls.__topeaks(frame)
        dist  = cls.__distances(distances, constraints, peaks)
        best  = {key: min(val, key = val.__getitem__) for key, val in dist.items()}
        fcn   = partial(cls.__beadoutput, peaks, dist, peakids)
        for hpname in sorted(set(best.values()), key = lambda x: x or chr(255)):
            vals = (fcn(*item) for item in best.items() if item[1] == hpname)
            yield ByHairpinGroup(hpname, sorted(vals, key = lambda i: i[1], reverse = True))

    def run(self, args):
        cnf   = self.config()
        elems = 'distances', 'constraints', 'peakids'
        args.apply(partial(self.apply, *(cnf[i] for i in elems)))

    @classmethod
    def __topeaks(cls, frame:Iterable[Input]) -> _PEAKS:
        u"Regroups the beads from a frame by hairpin"
        def _get(evts):
            if isinstance(evts, Iterator):
                evts = tuple(evts)

            if len(evts) == 0:
                return np.empty((0,), dtype = 'f4'), np.empty((0,), dtype = 'O')

            if getattr(evts, 'dtype', 'O') == 'f4':
                return evts, np.empty((0,), dtype = 'O')
            else:
                return (np.array([i for i, _ in evts], dtype = 'f4'), evts)

        return {key: _get(evts) for key, evts in frame}

    @staticmethod
    def __distances(distances:Distances, constraints:Constraints, peaks:_PEAKS):
        def _compute(key, bead):
            cstr = constraints.get(key, None)
            if cstr is not None:
                hpin = distances.get(cstr[0], None)
                if hpin is not None:
                    return {cstr[0]: updatecopy(hpin, **cstr[1])(bead)}

            if len(bead) > 0:
                return {name: calc(bead) for name, calc in distances.items()}

            else:
                return {None: next(iter(distances.values()))(bead)}

        return {key: _compute(key, bead) for key, (bead, _) in peaks.items()}

    @staticmethod
    def __beadoutput(peaks   : _PEAKS,
                     dist    : Distances,
                     peakids : PeakIds,
                     beadkey : BEADKEY,
                     hpkey   : str
                    ) -> ByHairpinBead:
        bdist  = dist[beadkey]
        bpeaks = peaks[beadkey]

        if len(bdist) > 1:
            aval = bdist[hpkey].value
            bval = min(i[0] for k, i in bdist.items() if k != hpkey)
            silh = ((bval-aval)/max(aval, bval)-.5)*2.
        else:
            silh = 1. if len(bdist) == 1 else -3.

        alg = peakids.get(hpkey, PeakIdentifier())
        ids = alg(bpeaks[0], *bdist.get(hpkey, (0., 1., 0))[1:])
        return ByHairpinBead(beadkey, silh, bdist, ids, bpeaks[1])
