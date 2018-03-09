#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Matching experimental peaks to hairpins: tasks and processors"
from typing                   import Sequence, NamedTuple, Iterator, cast
from functools                import partial
from data.views               import BEADKEY, TrackView
from control.processor        import Processor
from control.processor.runner import pooledinput, pooldump
from peakfinding.peaksarray   import Output as PeakFindingOutput, PeaksArray
from ..tohairpin              import Distance
from .fittohairpin            import (FitToHairpinTask, FitToHairpinProcessor,
                                      Fitters, Constraints, Matchers, Input,
                                      PeakEventsTuple)


class BeadsByHairpinTask(FitToHairpinTask):
    "Groups beads per hairpin"

class ByHairpinBead(NamedTuple): # pylint: disable=missing-docstring
    key        : BEADKEY
    silhouette : float
    distance   : Distance
    peaks      : PeaksArray
    events     : PeakFindingOutput

class ByHairpinGroup(NamedTuple): # pylint: disable=missing-docstring
    key   : str
    beads : Sequence[ByHairpinBead]

class BeadsByHairpinProcessor(Processor[BeadsByHairpinTask]):
    "Groups beads per hairpin"
    CHILD = FitToHairpinProcessor
    @staticmethod
    def canpool():
        "returns whether this is pooled"
        return True

    @staticmethod
    def _apply(app, frame):
        return frame.new(TrackView).selecting(app)

    @classmethod
    def apply(cls, toframe = None, data = None, pool = None, **cnf):
        "applies the task to a frame or returns a function that does so"
        if pool is None:
            app = partial(cls._unpooled, cnf)
        else:
            app = partial(cls._pooled, pool, pooldump(data.append(cls.CHILD(cnf))))

        return partial(cls._apply, app) if toframe is None else cls._apply(app, toframe)

    def run(self, args):
        "updates frames"
        args.apply(self.apply(**args.poolkwargs(self.task), **self.config()))

    @classmethod
    def compute(cls,
                frame       : Input,
                fit         : Fitters     = None,
                constraints : Constraints = None,
                match       : Matchers    = None
               ) -> Iterator[ByHairpinGroup]:
        "Regroups the beads from a frame by hairpin"
        cnf = cls.CHILD.keywords(dict(fit         = fit,
                                      constraints = constraints,
                                      match       = match))
        fcn = partial(cls.CHILD.compute, **cnf)
        itr = cast(Iterator[PeakEventsTuple], frame)
        yield from cls.__output(dict(fcn(i) for i in itr))

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
    def _unpooled(cls, cnf, frame):
        vals       = {i: cnf[i] for i in set(cnf) & {'fit', 'constraints', 'match'}}
        frame.data = {i.key: i for i in cls.compute(frame.data, **vals)}
        return []

    @classmethod
    def _pooled(cls, pool, pickled, frame):
        out        = cls.__output(pooledinput(pool, pickled, frame.data))
        frame.data = {i.key: i for i in out}
        return []
