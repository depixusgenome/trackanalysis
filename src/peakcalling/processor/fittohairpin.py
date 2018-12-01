#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Matching experimental peaks to hairpins: tasks and processors"
from   typing                      import (Dict, List, Sequence, NamedTuple,
                                           Type, Iterator, Tuple, Union, Optional,
                                           Iterable, Any, cast)

import numpy                       as     np

from   control.processor.taskview  import TaskViewProcessor
from   control.processor.dataframe import DataFrameFactory
from   data.views                  import BEADKEY, TaskView, TrackView
from   model                       import Task, Level
from   peakfinding.peaksarray      import (Output as PeakFindingOutput,
                                           PeakListArray, PeaksArray)
from   peakfinding.processor       import (PeaksDict, SingleStrandTask,
                                           BaselinePeakTask, SingleStrandProcessor,
                                           BaselinePeakProcessor)
from   utils                       import (StreamUnion, initdefaults, updatecopy,
                                           asobjarray, DefaultValue)
from   ..tohairpin                 import (HairpinFitter, PeakGridFit, Distance,
                                           PeakMatching, Pivot, PEAKS_TYPE)
from   .._base                     import Range

class DistanceConstraint(NamedTuple): # pylint: disable=missing-docstring
    hairpin     : Optional[str]
    constraints : Dict[str, Range]

Fitters     = Dict[str,     HairpinFitter]
Constraints = Dict[BEADKEY, DistanceConstraint]
Matchers    = Dict[str,     PeakMatching]

class FitToHairpinTask(Task):
    """
    Fits a bead to all provided hairpins.

    # Attributes

    * `fit`: a dictionnary of specific `HairpinFitter` to use for a bead.
    `DEFAULT_FIT` is used when none is provided for a given bead.

    * `constraints`: a dictionnary of specific constraints to apply for a bead.
    `DEFAULT_CONSTRAINTS` is used when none are provided for a given bead.

    * `match`: a dictionnary of specific `PeakMatching` to use for a bead.
    `DEFAULT_MATCH` is used when none is provided for a given bead.

    See `peakcalling.tohairpin` for the various available `HairpinFitter`.

    # Returned values:

    Values are returned per bead  in a `FitBead` object:

    * `key`: the bead number

    * `silhouette`: an indicator of how far above the best fit is to its
    others.  A value close to 1 indictes that the bead is identified
    unambiguously with a single hairpin sequence.

    * `distances`: one `Distance` item per hairpin sequence. The hairpin with
    the lowest `Distance.value` is the likeliest fit.

    * `peaks      : the peak position in nm together with the hairpin peak it's affected to.
    * `events     : peak events as out of an `Events` view.
    """
    level                           = Level.peak
    fit         : Fitters           = dict()
    constraints : Constraints       = dict()
    match       : Matchers          = dict()
    pullphaseratio: Optional[float] = .88
    singlestrand: SingleStrandTask  = SingleStrandTask()
    baseline    : BaselinePeakTask  = BaselinePeakTask()
    DEFAULT_FIT                     = PeakGridFit
    DEFAULT_MATCH                   = PeakMatching
    DEFAULT_CONSTRAINTS             = dict(
        stretch = Range(None, 0.1,  10.),
        bias    = Range(None, 1e-4, 3e-3)
    )

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
        if not fit or fit is DefaultValue:
            fits = dict(cls.DEFAULT_FIT.read(path, oligos))
        elif isinstance(fit, type):
            fits = dict(cast(Type[HairpinFitter], fit).read(path, oligos))
        else:
            ifit = cast(HairpinFitter, fit)
            fits = {i: updatecopy(ifit, True,
                                  peaks      = j.peaks,
                                  strandsize = j.strandsize)
                    for i, j in ifit.read(path, oligos)}

        imatch = (cls.DEFAULT_MATCH() if not match or match is DefaultValue else
                  cast(Type[PeakMatching], match)() if isinstance(match, type) else
                  cast(PeakMatching, match))

        return cls(fit   = fits,
                   match = {key: updatecopy(imatch, True,
                                            peaks      = value.peaks,
                                            strandsize = value.strandsize)
                            for key, value in fits.items()})

PeakEvents      = Iterable[PeakFindingOutput]
PeakEventsTuple = Tuple[BEADKEY, PeakEvents]
_PEAKS          = Tuple[np.ndarray, PeakListArray]
Input           = Union[PeaksDict, PeakEvents]
class FitBead(NamedTuple): # pylint: disable=missing-docstring
    key        : BEADKEY
    silhouette : float
    distances  : Dict[Optional[str], Distance]
    peaks      : PEAKS_TYPE
    events     : PeakListArray

class FitToHairpinDict(TaskView[FitToHairpinTask, BEADKEY]): # pylint: disable=too-many-ancestors
    "iterator over peaks grouped by beads"
    level  = Level.bead
    def beadextension(self, ibead) -> Optional[float]:
        """
        Return the median bead extension (phase 3 - phase 1)
        """
        return getattr(self.data, 'beadextension', lambda *_: None)(ibead)

    def phaseposition(self, phase: int, ibead:BEADKEY) -> Optional[float]:
        """
        Return the median position for a given phase
        """
        return getattr(self.data, 'phaseposition', lambda *_: None)(phase, ibead)

    @staticmethod
    def __topeaks(aevts:PeakEvents) -> PeakListArray:
        "Regroups the beads from a frame by hairpin"
        if not isinstance(aevts, Iterator):
            evts = cast(Sequence[PeakFindingOutput], aevts)
            if getattr(evts, 'dtype', 'O') == 'f4':
                return PeakListArray([(i, PeaksArray([])) for i in evts])
        else:
            evts = tuple(aevts)

        disc = (getattr(evts, 'discarded', 0) if hasattr(evts, 'discarded') else
                0                             if len(evts) == 0             else
                getattr(evts[0][1], 'discarded', 0))
        evts = asobjarray(((i, asobjarray(j)) for i, j in evts),
                          view      = PeakListArray,
                          discarded = disc).astype(getattr(PeakListArray, '_dtype'))
        return cast(PeakListArray, evts)

    @classmethod
    def _transform_ids(cls, sel):
        return cls._transform_to_bead_ids(sel)

    def __distances(self, key: BEADKEY, inp:PeakListArray)->Dict[Optional[str], Distance]:
        fits = dict(self.config.fit)
        cstr = self.config.constraints.get(key, None)
        hpin = None if cstr is None else fits.get(cast(str, cstr[0]), None)
        if cstr is not None:
            if hpin is not None:
                fits = {cast(str, cstr[0]): hpin}
            fits = {i: updatecopy(j, **cstr[1]) for i, j in fits.items()}

        # discard fits that have a hairpin size either too small or too big
        if hpin is None and self.config.pullphaseratio is not None:
            extent = self.beadextension(key)
            if extent is not None:
                extent *= self.config.pullphaseratio
                fits    = {i: j for i, j in fits.items() if j.withinrange(extent)}

        args = cast(TrackView, self.data), key, inp
        if any(i.hassinglestrand for i in fits.values()):
            strand = SingleStrandProcessor(task = self.config.singlestrand).detected(*args)
            if strand is True:
                # single-strand found: use it as a pivot
                fits.update((i, updatecopy(j, pivot = Pivot.top))
                            for i, j in fits.items() if j.hassinglestrand)
            elif strand is False:
                # single-strand found as missing: discard it from fit
                fits.update((i, updatecopy(j, peaks = j.peaks[:-1]))
                            for i, j in fits.items() if j.hassinglestrand)

        if BaselinePeakProcessor(task = self.config.baseline).detected(*args) is False:
            # baseline missing: don't use it as a pivot
            fits.update((i, updatecopy(j, pivot = Pivot.absolute))
                        for i, j in fits.items() if not j.hassinglestrand)

        bead = inp['peaks']
        return {name: calc.optimize(bead) for name, calc in fits.items()}

    def __beadoutput(self,
                     key     : BEADKEY,
                     events  : PeakListArray,
                     dist    : Dict[Optional[str], Distance],
                    ) -> FitBead:
        if len(dist) == 0:
            return FitBead(key, -1., dist, PeakMatching.empty(events['peaks']), events)

        best = cast(str, min(dist, key = dist.__getitem__))
        silh = HairpinFitter.silhouette(dist, best)
        alg  = self.config.match.get(best, self.config.DEFAULT_MATCH())
        ids  = alg.pair(events['peaks'], *dist.get(best, (0., 1., 0))[1:])
        return FitBead(key, silh, dist, ids, events)

    # pylint: disable=arguments-differ
    def compute(self, aitem: Union[BEADKEY, PeakEventsTuple]) -> FitBead:
        "Action applied to the frame"
        if isinstance(aitem, BEADKEY):
            bead = cast(BEADKEY, aitem)
            inp  = cast(PeakEvents, cast(dict, self.data)[bead])
        else:
            bead, inp = cast(PeakEventsTuple, aitem)


        events = self.__topeaks(inp)
        dist   = self.__distances(bead, events)
        return self.__beadoutput(bead, events, dist)

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

@DataFrameFactory.adddoc
class FitsDataFrameFactory(DataFrameFactory[FitToHairpinDict]):
    """
    Transform a `FitToHairpinDict` to one or more `pandas.DataFrame`.

    The dataframe contains one row per event selected in a peak.

    # Default Columns

    * *peak*: the peak position in nm to which the event belongs
    * the peak position in base number for each hairpin provided. The name of
    the column is that of the hairpin.
    """
    # pylint: disable=arguments-differ
    @staticmethod
    def _run(_1, _2, res:FitBead) -> Dict[str, np.ndarray]: # type: ignore
        out: Dict[str, List[np.ndarray]] = {i: [] for i in ('cycle', 'peak', 'avg', 'start')}
        for (peak, evts) in res.events:
            for i, evt in enumerate(cast(Iterator[np.ndarray], evts)):
                if len(evt):
                    out['cycle'].append(np.full(len(evt), i,    dtype = 'i4'))
                    out['peak'] .append(np.full(len(evt), peak, dtype = 'f4'))
                    out['avg']  .append([np.nanmean(j) for j in evt['data']])
                    out['start'].append(evt['start'])
        out2 = {i: np.concatenate(j) for i, j in out.items()}
        out2.update({cast(str, i): (out2['avg']-j.bias)*j.stretch
                     for i, j in res.distances.items()})
        return out2
