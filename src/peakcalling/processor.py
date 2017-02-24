#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"""
Matching experimental peaks to hairpins: tasks and processors
"""
from   typing       import (Dict, Sequence, NamedTuple, # pylint: disable=unused-import
                            Iterator, Tuple, Union, Any, Iterable, cast)
from   functools    import partial
import numpy        as np

from utils                  import StreamUnion, initdefaults, updatecopy
from data.trackitems        import BEADKEY
from peakfinding.selector   import Output as PeakFindingOutput
from model              import Task, Level
from control.processor  import Processor
from .tohairpin         import HairpinDistance, Distance

DistanceConstraint = NamedTuple('DistanceConstraint',
                                [('hairpin', str), ('constraints', dict)])
class BeadsByHairpinTask(Task):
    u"Groups beads per hairpin"
    level       = Level.peak
    hairpins    = dict()    # type: Dict[str,     HairpinDistance]
    constraints = dict()    # type: Dict[BEADKEY, DistanceConstraint]
    @initdefaults
    def __init__(self, **_):
        super().__init__()

    @classmethod
    def read(cls, path : StreamUnion, oligos : Sequence[str]) -> 'BeadsByHairpinTask':
        u"creates a BeadsByHairpin from a fasta file and a list of oligos"
        return cls(hairpins = dict(HairpinDistance.read(path, oligos)))

BeadsByHairpinResults = NamedTuple('BeadsByHairpinResults',
                                   [('key',        Any),
                                    ('silhouette', float),
                                    ('distance',   Distance),
                                    ('events',     Sequence[PeakFindingOutput])])

Input  = Tuple[BEADKEY, Iterable[PeakFindingOutput]]
Output = Tuple[str, Sequence[BeadsByHairpinResults]]
class BeadsByHairpinProcessor(Processor):
    u"Groups beads per hairpin"
    tasktype = BeadsByHairpinTask
    @classmethod
    def topeaks(cls, frame:Iterable[Input]
               ) -> Dict[BEADKEY, Tuple[Sequence[float], Sequence[PeakFindingOutput]]]:
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
    def silhouette(best:str, results:dict) -> float:
        u"Returns a grade for these results"
        if len(results) == 0:
            return -3.
        if len(results) == 1:
            return 1.
        aval = results[best].value
        bval = min(i[0] for k, i in results.items() if k != best)
        return ((bval-aval)/max(aval, bval)-.5)*2.

    @classmethod
    def apply(cls,
              hpins         : Dict,
              constraints   : Dict[BEADKEY, DistanceConstraint],
              frame         : Iterable[Tuple[BEADKEY, Iterable[Input]]]
             ) -> Iterator[Output]:
        u"Regroups the beads from a frame by hairpin"
        peaks = cls.topeaks(frame)

        dist  = cls.__distances(hpins, constraints, peaks)
        best  = {key: min(vals, key = vals.__getitem__)
                 for key, vals in dist.items()}

        _res  = BeadsByHairpinResults
        res   = lambda i, k, d: _res(k, cls.silhouette(i, d), d[i], peaks[k][1])

        for name in sorted(set(best.values()), key = lambda x: x or chr(255)):
            vals = [res(i, k, dist[k]) for k, i in best.items() if i == name]
            yield (name, sorted(vals, key = lambda i: i[1], reverse = True))

    def run(self, args):
        cnf = self.config()
        args.apply(partial(self.apply, cnf['hairpins'], cnf['constraints']))

    @staticmethod
    def __distances(hpins, constraints, peaks):
        def _compute(key, bead):
            cstr = constraints.get(key, None)
            if cstr is not None:
                hpin = hpins.get(cstr[0], None)
                if hpin is not None:
                    return {cstr[0]: updatecopy(hpin, **cstr[1])(bead)}

            if len(bead) > 0:
                return {name: calc(bead) for name, calc in hpins.items()}

            else:
                return {None: next(iter(hpins.values()))(bead)}

        return {key: _compute(key, bead) for key, (bead, _) in peaks.items()}
