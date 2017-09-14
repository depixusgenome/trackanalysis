#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Matching experimental peaks to hairpins: tasks and processors"
from typing                   import Sequence, NamedTuple, Iterator
from functools                import partial
from data.views               import BEADKEY, TrackView
from control.processor        import Processor
from control.processor.runner import pooledinput, pooldump
from peakfinding.selector     import Output as PeakFindingOutput
from ..tohairpin              import Distance, PEAKS_TYPE
from .fittohairpin            import (FitToHairpinTask, FitToHairpinProcessor,
                                      Distances, Constraints, PeakIds, Input)


class BeadsByHairpinTask(FitToHairpinTask):
    "Groups beads per hairpin"

class ByHairpinBead(NamedTuple): # pylint: disable=missing-docstring
    key        : BEADKEY
    silhouette : float
    distance   : Distance
    peaks      : PEAKS_TYPE
    events     : PeakFindingOutput

class ByHairpinGroup(NamedTuple): # pylint: disable=missing-docstring
    key   : str
    beads : Sequence[ByHairpinBead]

class BeadsByHairpinProcessor(Processor):
    "Groups beads per hairpin"
    CHILD = FitToHairpinProcessor
    @staticmethod
    def canpool():
        return True

    @classmethod
    def apply(cls, toframe = None, data = None, pool = None, **cnf):
        "applies the task to a frame or returns a function that does so"
        if pool is None:
            app = partial(cls.__unpooled, cnf)
        else:
            app = partial(cls.__pooled, pool, pooldump(data.append(cls.CHILD(cnf))))

        fcn = lambda j: j.new(TrackView, data = lambda: app(j))
        return fcn if toframe is None else fcn(toframe)

    def run(self, args):
        args.apply(self.apply(**args.poolkwargs(self.task), **self.config()))

    @classmethod
    def compute(cls,
                dist  : Distances,
                cstr  : Constraints,
                ids   : PeakIds,
                frame : Input
               ) -> Iterator[ByHairpinGroup]:
        "Regroups the beads from a frame by hairpin"
        fcn = cls.CHILD.compute
        yield from cls.__output(dict(fcn(i, dist, cstr, ids) for i in frame))

    @classmethod
    def __output(cls, out) -> Iterator[ByHairpinGroup]:
        one  = lambda i, j: ByHairpinBead(i[0], i[1], i[2][j], i[3], i[4])
        best = {itm.key: min(itm.distances, key = itm.distances.__getitem__)
                for itm in out.values()}
        for hpname in sorted(set(best.values()), key = lambda x: x or chr(255)):
            vals = (one(val, hpname) for key, val in out.items() if best[key] == hpname)
            yield ByHairpinGroup(hpname,
                                 sorted(vals,
                                        key     = lambda i: i.silhouette,
                                        reverse = True))

    @classmethod
    def __unpooled(cls, cnf, frame):
        vals = (cnf.get(i, {}) for i in ('distances', 'constrainst', 'peakids'))
        return {i.key: i for i in cls.compute(*vals, frame)}

    @classmethod
    def __pooled(cls, pool, pickled, frame):
        out  = cls.__output(pooledinput(pool, pickled, frame))
        return {i.key: i for i in out}
