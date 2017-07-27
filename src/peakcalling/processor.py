#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Matching experimental peaks to hairpins: tasks and processors"
from   typing       import (Dict, Sequence, NamedTuple,
                            Iterator, Tuple, Union, Iterable, Optional)
from   functools    import partial
import numpy        as np

from utils                      import StreamUnion, initdefaults, updatecopy, asobjarray
from data.trackitems            import BEADKEY, TrackItems, Beads
from peakfinding.selector       import Output as PeakFindingOutput, PeaksArray
from peakfinding.processor      import PeaksDict
from model                      import Task, Level
from control.processor          import Processor
from control.processor.runner   import pooledinput, pooldump
from .tohairpin                 import (HairpinDistance, Distance,
                                        PeakIdentifier, PEAKS_TYPE)

DistanceConstraint = NamedTuple('DistanceConstraint',
                                [('hairpin', str), ('constraints', dict)])

Distances   = Dict[str,     HairpinDistance]
Constraints = Dict[BEADKEY, DistanceConstraint]
PeakIds     = Dict[str,     PeakIdentifier]

class FitToHairpinTask(Task):
    "Fits a bead to all hairpins"
    level       = Level.peak
    distances   = dict() # type: Distances
    constraints = dict() # type: Constraints
    peakids     = dict() # type: PeakIds
    @initdefaults(frozenset(locals()) - {'level'})
    def __init__(self, **kwa):
        super().__init__()
        if 'sequence' in kwa:
            assert 'oligo' in kwa
            other = self.read(kwa['sequence'], kwa['oligo'],
                              distance   = kwa.get('distance',   None),
                              identifier = kwa.get('identifier', None))
            self.distances.update(other.distances)
            self.peakids.update(other.peakids)

    def __scripting__(self, kwa):
        if 'sequence' in kwa:
            other = self.read(kwa['sequence'], kwa['oligo'],
                              distance   = kwa.get('distance',   None),
                              identifier = kwa.get('identifier', None))
            self.distances.update(other.distances)
            self.peakids.update(other.peakids)
            return self

    @classmethod
    def isslow(cls) -> bool:
        "whether this task implies long computations"
        return True

    @classmethod
    def read(cls,
             path   : StreamUnion,
             oligos : Sequence[str],
             distance:   HairpinDistance = None,
             identifier: PeakIdentifier  = None
            ) -> 'FitToHairpinTask':
        "creates a BeadsByHairpin from a fasta file and a list of oligos"
        items = dict(HairpinDistance.read(path, oligos))
        if distance is not None:
            items = {i: updatecopy(distance, True, peaks = j.peaks)
                     for i, j in items.items()}

        if identifier is None:
            identifier = PeakIdentifier()
        return cls(distances = items,
                   peakids   = {key: updatecopy(identifier, True, peaks = value.peaks)
                                for key, value in items.items()})

class BeadsByHairpinTask(FitToHairpinTask):
    "Groups beads per hairpin"

Input   = Union[PeaksDict, Iterable[Tuple[BEADKEY,np.ndarray]]]
_PEAKS  = Tuple[Sequence[float], Sequence[PeakFindingOutput]]
FitBead = NamedTuple('FitBead',
                     [('key',         BEADKEY),
                      ('silhouette',  float),
                      ('distances',   Dict[Optional[str], Distance]),
                      ('peaks',       PEAKS_TYPE),
                      ('events',      PeakFindingOutput)])


class FitToHairpinDict(TrackItems):
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
        self.__keys = None

    def _keys(self, sel:Sequence = None, _ = None) -> Iterator[BEADKEY]:
        if self.__keys is None:
            self.__keys = frozenset(self.data.keys())

        if sel is None:
            yield from self.__keys
        else:
            yield from (i for i in self.__keys if i in sel)

    def _iter(self, sel:Sequence = None) -> Iterator[Tuple[BEADKEY, FitBead]]:
        yield from ((bead, self.compute(bead)) for bead in self.keys(sel))

    @staticmethod
    def __topeaks(evts:Sequence[PeakFindingOutput]) -> _PEAKS:
        "Regroups the beads from a frame by hairpin"
        if isinstance(evts, Iterator):
            evts = tuple(evts)

        if getattr(evts, 'dtype', 'O') == 'f4':
            return evts, PeaksArray([], dtype = 'O')

        disc = (getattr(evts, 'discarded', 0) if hasattr(evts, 'discarded') else
                0                             if len(evts) == 0             else
                getattr(evts[0][1], 'discarded', 0))
        evts = asobjarray(((i, asobjarray(j)) for i, j in evts),
                          view      = PeaksArray,
                          discarded = disc)
        return np.array([i for i, _ in evts], dtype = 'f4'), evts

    def __distances(self, key: str, bead: Sequence[float])->Dict[Optional[str], Distance]:
        distances   = self.config.distances
        constraints = self.config.constraints
        cstr = constraints.get(key, None)
        if cstr is not None:
            hpin = distances.get(cstr[0], None)
            if hpin is not None:
                return {cstr[0]: updatecopy(hpin, **cstr[1]).optimize(bead)}

        if len(bead) > 0:
            return {name: calc.optimize(bead) for name, calc in distances.items()}

        return {None: next(iter(distances.values())).optimize(bead)}

    def __beadoutput(self,
                     key     : BEADKEY,
                     peaks   : Sequence[float],
                     events  : Sequence[PeakFindingOutput],
                     dist    : Dict[Optional[str], Distance],
                    ) -> FitBead:
        best = min(dist, key = dist.__getitem__)
        silh = HairpinDistance.silhouette(dist, best)
        alg  = self.config.peakids.get(best, PeakIdentifier())
        ids  = alg.pair(peaks, *dist.get(best, (0., 1., 0))[1:])
        return FitBead(key, silh, dist, ids, events)

    def compute(self, item: Union[BEADKEY, Tuple[BEADKEY,Sequence[PeakFindingOutput]]]) -> FitBead:
        "Action applied to the frame"
        if Beads.isbead(item):
            item = item, self.data[item]

        peaks, events = self.__topeaks(item[1])
        dist          = self.__distances(item[0], peaks)
        return self.__beadoutput(item[0], peaks, events, dist)

class FitToHairpinProcessor(Processor):
    "Groups beads per hairpin"
    @classmethod
    def apply(cls, toframe = None, **cnf):
        "applies the task to a frame or returns a function that does so"
        fcn = lambda frame: frame.new(FitToHairpinDict, config = cnf)
        return fcn if toframe is None else fcn(toframe)

    @classmethod
    def compute(cls,
                item        : Tuple[BEADKEY,Sequence[PeakFindingOutput]],
                distances   : Optional[Distances]   = None,
                constraints : Optional[Constraints] = None,
                peakids     : Optional[PeakIds]     = None,
                **cnf
               ) -> Tuple[BEADKEY,FitBead]:
        "Action applied to the frame"
        cnf.update(distances   = {} if distances   is None else distances, # type: ignore
                   constraints = {} if constraints is None else constraints,
                   peakids     = {} if peakids     is None else peakids)
        out = FitToHairpinDict(config = cnf).compute(item)
        return out.key, out

    def run(self, args):
        args.apply(self.apply(**self.config()))

ByHairpinBead  = NamedTuple('ByHairpinBead',
                            [('key',         BEADKEY),
                             ('silhouette',  float),
                             ('distance',    Distance),
                             ('peaks',       PEAKS_TYPE),
                             ('events',      PeakFindingOutput)])
ByHairpinGroup = NamedTuple('ByHairpinGroup',
                            [('key', str), ('beads', Sequence[ByHairpinBead])])

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

        fcn = lambda j: j.new(TrackItems, data = lambda: app(j))
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
    def __output(cls, out):
        one  = lambda i, j: ByHairpinBead(*i[:2], i[2][j], *i[3:])
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
