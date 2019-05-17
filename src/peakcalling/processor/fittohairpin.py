#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Matching experimental peaks to hairpins: tasks and processors"
from   typing                      import (
    Dict, Sequence, NamedTuple, List, Type, Iterator, Tuple, Union, Optional,
    Iterable, Any, Callable, cast
)

import numpy                       as     np

from   data.views                  import BEADKEY, TaskView, TrackView
from   peakfinding.peaksarray      import (
    Output as PeakFindingOutput, PeakListArray, PeaksArray
)
from   peakfinding.processor       import (
    PeaksDict, SingleStrandTask, BaselinePeakTask, SingleStrandProcessor,
    BaselinePeakProcessor
)
from   peakfinding.processor.dataframe import PeaksDataFrameFactory
from   taskmodel                       import Task, Level
from   taskcontrol.processor.taskview  import TaskViewProcessor
from   taskcontrol.processor.dataframe import DataFrameFactory, DataFrameTask
from   utils                       import (
    StreamUnion, initdefaults, updatecopy, asobjarray, DefaultValue, isint
)
from   ..tohairpin                 import (
    HairpinFitter, PeakGridFit, Distance, PeakMatching, Pivot, PEAKS_TYPE
)
from   .._base                     import Range

class DistanceConstraint(NamedTuple):
    hairpin     : Optional[str]
    constraints : Dict[str, Range]
    def rescale(self, value:float) -> 'DistanceConstraint':
        "rescale factors (from µm to V for example) for a given bead"
        return type(self)(
            self.hairpin,
            {i: j.rescale(i, value) for i, j in self.constraints.items()}
        )

Fitters     = Dict[str,     HairpinFitter]
Constraints = Dict[BEADKEY, DistanceConstraint]
Matchers    = Dict[str,     PeakMatching]

class FitToHairpinTask(Task, zattributes = ('fit', 'constraints', 'singlestrand', 'baseline')):
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
class FitBead(NamedTuple):
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
        "converts PeakEvents to PeakListArray"
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

    def distances(
            self,
            key: BEADKEY,
            inp: Optional[PeakListArray] = None
    )->Dict[Optional[str], Distance]:
        "compute distances from peak data"
        if inp is None:
            inp = self.__topeaks(cast(PeakEvents, cast(dict, self.data)[key]))
        bead = inp['peaks']
        return {name: calc.optimize(bead) for name, calc in self.fits(key, inp).items()}

    def fits(
            self,
            key: BEADKEY,
            inp: Optional[PeakListArray] = None
    ) -> Dict[Optional[str], HairpinFitter]:
        "compute distances from peak data"
        if inp is None:
            inp = self.__topeaks(cast(PeakEvents, cast(dict, self.data)[key]))

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

        return fits

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
        if isint(aitem):
            bead = cast(BEADKEY, aitem)
            inp  = cast(PeakEvents, cast(dict, self.data)[bead])
        else:
            bead, inp = cast(PeakEventsTuple, aitem)


        events = self.__topeaks(inp)
        dist   = self.distances(bead, events)
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

    The dataframe contains one row per bead and valid hairpin.

    # Default Columns

    * hpin:           the hairpin name.
    * cost:           the cost value for fitting to that hairpin.
    * stretch:        the stretch value from fitting to that hairpin.
    * bias:           the bias value from fitting to that hairpin.
    * nbindings:      the number of expected bindings on the hairpin.
    * nblockages:     the number of blockage positions detected on the bead.
    * hfsigma:        the high frequency noise for that bead.
    * considering blockage positions versus expected bindings:
        * beadfalsepos:   the number of formers not assigned to any of the latters.
        * beadfalseneg:   the number of latters without assignees.
        * beadtruepos:    the number of assigned formers.
        * beadresiduals:  the mean distance from a former to its assigned latter.
        * beadduplicates: the number of assigned formers less the number of assigned latters.
    * considering expected bindings versus blockage positions:
        * hpinfalsepos:   the number of formers not assigned to any of the latters.
        * hpinfalseneg:   the number of latters without assignees.
        * hpintruepos:    the number of assigned formers.
        * hpinresiduals:  the mean distance from a former to its assigned latter.
        * hpinduplicates: the number of assigned formers less the number of assigned latters.
    * For identified blockage positions:
        * tpaverageduration:   the average event duration
        * tphybridisationrate: the average event rate
        * tpeventcount:        the average event count
    * For non-identified blockage positions:
        * fpaverageduration:   the average event duration
        * fphybridisationrate: the average event rate
        * fpeventcount:        the average event count

    # Configuration

    The following can be provided to the `measures` dictionnary of the task

    * aggregator: Union[str, Callable[[Sequence[float]], float]
        the aggregator to use, `np.nanmedian` by default.
    * distances: Dict[str, float]
        A dictionnary containing:
        ```
        {
            'bead': max distance from blockage positions to an expected binding,
            'hpin': max distance from expected bindings to a blockage position.
        }
        ```
    * peaks: Dict[str, Any]
        A dictionnary passed to a PeaksDataFrameFactory. The latter will
        measure statistics on true positives and false positives, then report
        the results aggregated by bead and hairpin.
    * optionals: Dict[str, Callable[[FitToHairpinDict, int, FitBead], np.ndarray]]
        A dictionnary for creating additional columns. The functions take 3 arguments,
        the view, the bead id, and the results for that bead.
    """
    # pylint: disable=arguments-differ
    def __init__(
            self,
            task,
            frame:     FitToHairpinDict,
            **kwa:     Callable[[FitToHairpinDict, int, FitBead], np.ndarray]
    ):
        super().__init__(task, frame)
        meas                               = dict(task.measures, **kwa)
        distances                          = meas.pop('distances', None)
        self.__distances: Dict[str, float] = (
            {
                i: float(cast(int, distances))
                for i in ('bead', 'hpin')
            } if np.isscalar(distances) else

            {
            } if distances is None      else

            {
                str(i): float(j)
                for i, j in dict(cast(dict, distances)).items()
            }
        )

        peaks = DataFrameTask(measures = meas.pop('peaks', {}))
        self.__peaks: PeaksDataFrameFactory = (
            PeaksDataFrameFactory(peaks, frame)
            .discardcolumns('track', 'bead', 'cycle', 'avg', 'peakposition')
        )
        self.__aggregator: Callable[[Sequence[float]], float] = cast(
            Callable[[Sequence[float]], float],
            self.getfunction(meas.pop('aggregator', 'median'))
        )
        self.__optionals:                                                      \
            Dict[str, Callable[[FitToHairpinDict, int, FitBead], np.ndarray]]  \
            = meas

    def _run(
            self,
            frame: FitToHairpinDict,
            bead:  int,
            res:   FitBead
    ) -> Dict[str, np.ndarray]: # type: ignore
        frame = self.__config(frame)
        fits  = frame.fits(bead, res.events)
        out   = self.__basic(frame, bead, res, fits)
        out.update(self.__complex(frame, res, fits))
        out.update({i: j(frame, bead, res) for i, j in self.__optionals.items()})
        return out

    @staticmethod
    def __config(frame: FitToHairpinDict) -> FitToHairpinDict:
        cur   = frame
        first = None
        while hasattr(cur, 'data'):
            if isinstance(getattr(cur, 'config', None), FitToHairpinTask):
                first = cur
            cur = cur.data

        if not first:
            raise AttributeError(
                "Dataframe can only be created if"
                +" a FitToHairpinTask is in the tasklist"
            )
        return cast(FitToHairpinDict, first)

    @staticmethod
    def __basic(
            frame: FitToHairpinDict,
            bead:  int,
            res:   FitBead,
            fits:  Dict[Optional[str], HairpinFitter]
    ) -> Dict[str, np.ndarray]:
        size = len(res.distances)
        return {
            'hpin'      : np.array(list(res.distances),                    dtype = '<U20'),
            'cost'      : np.array([i[0] for i in res.distances.values()], dtype = 'f4'),
            'stretch'   : np.array([i[1] for i in res.distances.values()], dtype = 'f4'),
            'bias'      : np.array([i[2] for i in res.distances.values()], dtype = 'f4'),
            'nbindings' : np.array([i.peaks.size for i in fits.values()],  dtype = 'i4'),
            'nblockages': np.full (size, len(res.events),                  dtype = 'i4'),
            'hfsigma'   : np.full (size, frame.track.rawprecision(bead),   dtype = 'f4')
        }

    def __complex(
            self,
            frame: FitToHairpinTask,
            res:   FitBead,
            fits:  Dict[Optional[str], HairpinFitter],
    ) -> Dict[str, np.ndarray]:
        out: Dict[str, List[float]] = {}
        dist                        = res.distances
        for tpe in ('bead', 'hpin'):
            for hpin, alg in fits.items():
                good = self.__bead_hpin_complex(
                    tpe,
                    out,
                    self.__pks_complex(res, dist, hpin, alg),
                    self.__dist_complex(tpe, hpin, frame.config)
                )
                if tpe != 'hpin':
                    self.__tp_fp_complex(out, frame, res, good)
        return out
    @staticmethod
    def __pks_complex(res, dist, hpin, alg) -> Tuple[np.ndarray, np.ndarray]:
        return (
            (res.events['peaks']-dist[hpin][2])*dist[hpin][1],
            alg.peaks
        )

    def __dist_complex(self, tpe: str, hpin: Optional[str], config: FitToHairpinTask) -> float:
        return (
            self.__distances[tpe]       if tpe in self.__distances else
            config.match[hpin].window   if hpin in config.match    else
            config.DEFAULT_MATCH.window
        )

    def __bead_hpin_complex(
            self,
            tpe:  str,
            out:  Dict[str, List[float]],
            arrs: Tuple[np.ndarray, np.ndarray],
            dist: float
    ) -> np.ndarray:
        left  = np.concatenate([[-1e30], arrs[tpe == "bead"], [1e30]])
        right = arrs[tpe != "bead"]
        inds  = np.searchsorted(left, right)
        inds[left[inds]-right > right-left[inds-1]] -= 1

        good  = np.abs(left[inds]-right) < dist
        ids   = inds[good]-1

        out.setdefault(tpe+'truepos',    []).append(good.sum())
        out.setdefault(tpe+'falsepos',   []).append(good.size - good.sum())
        out.setdefault(tpe+'duplicates', []).append(good.size - np.unique(ids).size)
        out.setdefault(tpe+'residuals',  []).append(
            self.__aggregator(
                np.abs(arrs[tpe == 'bead'][ids]-arrs[tpe != 'bead'][good])
                **2
            )
        )
        return good

    def __tp_fp_complex(
            self,
            out: Dict[str, List[float]],
            frame:  FitToHairpinDict,
            res:    FitBead,
            good:   np.ndarray
    ):
        if frame.config.baseline:
            ind = (
                BaselinePeakProcessor(task = frame.config.baseline)
                .index(frame, res.key, res.events)
            )
        else:
            ind = None

        for fmt in ('tp', 'fp'):
            if ind is not None:
                # remove the baseline
                good[ind] = False
            data = self.__peaks.dictionary(frame, (res.key, res.events))
            for i, j in data.items():
                out.setdefault(fmt+i, []).append(self.__aggregator(j))
            good = np.logical_not(good)
