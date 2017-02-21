#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"""
Matching experimental peaks to hairpins: tasks and processors
"""
from   typing       import (Dict, Sequence, NamedTuple, # pylint: disable=unused-import
                            Iterator, Tuple, Any, cast)
from   functools    import partial
import numpy        as np

from utils              import StreamUnion, initdefaults
from model              import Task, Level
from control.processor  import Processor
from .tohairpin         import HairpinDistance, HairpinDistanceResults

class BeadsByHairpinTask(Task):
    u"Groups beads per hairpin"
    level    = Level.peak
    hairpins = dict()     # type: Dict[str, HairpinDistance]
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
                                    ('distances',  Dict[str, HairpinDistanceResults]),
                                    ('events',     np.ndarray)])

class BeadsByHairpinProcessor(Processor):
    u"Groups beads per hairpin"
    tasktype = BeadsByHairpinTask
    Output   = Iterator[Tuple[str, Sequence[BeadsByHairpinResults]]]
    @classmethod
    def topeaks(cls, frame):
        u"Regroups the beads from a frame by hairpin"
        def _get(evts):
            if isinstance(evts, Iterator):
                evts = tuple(evts)

            if len(evts) == 0:
                return np.empty((0,), dtype = 'f4'), np.empty((0,), dtype = 'O')

            if getattr(evts, 'dtype', 'O') == 'f4':
                return evts, np.empty((0,), dtype = 'O')
            else:
                return (np.array([i for i, _ in evts], dtype = 'f4'),
                        np.array([i for _, i in evts], dtype = 'O'))

        return {key: _get(evts) for key, evts in frame}

    @staticmethod
    def silhouette(best:str, results:dict) -> float:
        u"Returns a grade for these results"
        aval = results[best].value
        bval = min(i[0] for k, i in results.items() if k != best)
        return ((bval-aval)/max(aval, bval)-.5)*2.

    @classmethod
    def apply(cls, hpins, frame) -> 'BeadsByHairpinProcessor.Output':
        u"Regroups the beads from a frame by hairpin"
        peaks = cls.topeaks(frame)
        dist  = {key: {name: calc(bead) for name, calc in hpins.items()}
                 for key, (bead, _) in peaks.items() if len(bead) > 1}
        best  = {key: min(vals, key = vals.__getitem__)
                 for key, vals in dist.items()}

        args  = lambda i, k: (k, cls.silhouette(i, dist[k]), dist[k], peaks[k][1])

        for name in frozenset(tuple(best.values())):
            vals = [BeadsByHairpinResults(*args(i, k))
                    for k, i in best.items() if i == name]
            yield (name, sorted(vals, key = lambda i: i[1], reverse = True))

        vals = [BeadsByHairpinResults(k, -1., {}, peaks[k])
                for k in frozenset(peaks) - frozenset(best)]
        yield (None, vals)

    def run(self, args):
        args.apply(partial(self.apply, self.config()['hairpins']))
