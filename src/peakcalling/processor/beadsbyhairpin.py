#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Matching experimental peaks to hairpins: tasks and processors"
from typing                   import Sequence, NamedTuple, Iterator, cast
from functools                import partial
from data.views               import BEADKEY, TrackView
from control.processor        import Processor
from control.processor.runner import pooledinput, pooldump
from peakfinding.peaksarray   import Output as PeakFindingOutput, PeaksArray
from .._base                  import Distance, DEFAULT_BEST
from .fittohairpin            import (FitToHairpinTask, FitToHairpinProcessor,
                                      Fitters, Constraints, Matchers, Input,
                                      PeakEventsTuple)


class BeadsByHairpinTask(FitToHairpinTask):
    "Groups beads per hairpin"

class ByHairpinBead(NamedTuple):
    key        : BEADKEY
    silhouette : float
    distance   : Distance
    peaks      : PeaksArray
    events     : PeakFindingOutput

class ByHairpinGroup(NamedTuple):
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
            app = partial(cls._pooled, cnf, pool, pooldump(data.append(cls.CHILD(cnf))))

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
        yield from cls.__output(dict(fcn(i) for i in itr), cnf.get('constraints', {}))

    @classmethod
    def __output(cls, out, cstrs) -> Iterator[ByHairpinGroup]:
        dflt = BeadsByHairpinTask.DEFAULT_FIT().defaultparameters()
        one  = lambda i, j: ByHairpinBead(i[0], i[1], i[2].get(j, dflt), i[3], i[4])
        out  = {i: j for i, j in out.items() if not isinstance(j, Exception)}
        best = {itm.key: min(itm.distances, key = itm.distances.__getitem__, default = '✗')
                for itm in out.values()}
        for i, j  in best.items():
            if getattr(cstrs.get(i, None), 'hairpin', None) == j or j == '✗':
                # if it's a constraint, keep the user's choice
                continue
            if out[i].distances[j][0] == DEFAULT_BEST :
                best[i] = '✗'
        for hpname in sorted(set(best.values()), key = lambda x: x or chr(255)):
            vals = [one(val, hpname) for key, val in out.items() if best[key] == hpname]
            vals = sorted(vals, key = lambda i: i.silhouette, reverse = True)
            yield ByHairpinGroup(hpname, vals)

    @classmethod
    def _unpooled(cls, cnf, frame):
        vals       = {i: cnf[i] for i in set(cnf) & {'fit', 'constraints', 'match'}}
        frame.data = {i.key: i for i in cls.compute(frame.data, **vals)}
        return []

    @classmethod
    def _pooled(cls, cnf, pool, pickled, frame):
        out        = cls.__output(pooledinput(pool, pickled, frame.data, safe = True),
                                  cnf.get('constraints', {}))
        frame.data = {i.key: i for i in out}
        return []
