#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Matching experimental peaks to hairpins: tasks and processors"
from   copy                        import deepcopy
from   pathlib                     import Path
from   typing                      import (
    Dict, Sequence, NamedTuple, List, Type, Iterator, Tuple, Union, Optional,
    Iterable, Any, Callable, Pattern, ClassVar, cast
)

import numpy                       as     np
import pandas                      as     pd

from   data.views                  import BEADKEY, TaskView
from   peakfinding.peaksarray      import (
    Output as PeakFindingOutput, PeakListArray, PeaksArray
)
from   peakfinding.processor       import (
    PeaksDict, SingleStrandTask, BaselinePeakTask, SingleStrandProcessor,
    BaselinePeakProcessor
)
from   peakfinding.processor.dataframe import PeaksDataFrameFactory
from   sequences                       import splitoligos
from   taskmodel                       import Task, Level
from   taskcontrol.processor.taskview  import TaskViewProcessor
from   taskcontrol.processor.dataframe import DataFrameFactory, DataFrameTask
from   utils                       import (
    StreamUnion, initdefaults, updatecopy, asobjarray, DefaultValue, isint
)
from   utils.logconfig             import getLogger
from   ..tohairpin                 import (
    HairpinFitter, PeakGridFit, Distance, PeakMatching, Pivot, PEAKS_TYPE
)
from   .._base                     import Range

LOGS = getLogger(__name__)

class DistanceConstraint(NamedTuple):
    hairpin:     Optional[str]
    constraints: Dict[str, Range]

    def rescale(self, value:float) -> 'DistanceConstraint':
        "rescale factors (from µm to V for example) for a given bead"
        return type(self)(
            self.hairpin,
            {i: j.rescale(i, value) for i, j in self.constraints.items()}
        )


Fitters     = Dict[Optional[str], HairpinFitter]
Constraints = Dict[BEADKEY, DistanceConstraint]
Matchers    = Dict[Optional[str], PeakMatching]
Sequences   = Union[Dict[str, str], str, Path, None]
Oligos      = Union[str, List[str], None, Pattern]

class FitToHairpinTask(Task, zattributes = ('fit', 'constraints', 'singlestrand', 'baseline')):
    """
    Fits a bead to all provided hairpins.

    Attributes
    ----------
    fit:
        A dictionnary of specific `HairpinFitter` to use for a bead. If
        provided, the `None` keyword is used as the default value.
        `DEFAULT_FIT` is used when it isn't. See `peakcalling.tohairpin` for
        the various available `HairpinFitter`.

    constraints:
        A dictionnary of specific constraints to apply for a bead. If
        provided, the `None` keyword is used as the default value.
        `DEFAULT_CONSTRAINTS` is used when it isn't.

    match:
        A dictionnary of specific `PeakMatching` to use for a bead. If
        provided, the `None` keyword is used as the default value.
        `DEFAULT_MATCH` is used when it isn't.

    pullphaseratio:
        If provided, is used for estimating the bead's size in bases from phase
        3 and  discarding fit options with too different a size.

    singlestrand:
        If provided, the single-strand peak is looked for. If it is  found,
        fitting will use this rather than the baseline peak as the pivot for
        the fits.

    baseline:
        If provided, the baseline peak is looked for. If neither this nor the
        single-strand peak is found, then no pivot is used for fitting.

    sequences:
        The sequences or the path to a fasta file containing them. The fasta
        format is:

        ```
        > NAME1
        atcgactcatcg
        atcgactcatcg
        > NAME2
        atcgactcatcg
        atcgactcatcg
        ```

    oligos:
        The sequences or the path to a fasta file containing them. values can be:

        * a list of comma separated strings. These strings can contain
          'singlestrand' or '0' for fits using the single-strand or baseline
          peaks.
        * 'kmer': parses the track file names to find a kmer. The accepted
          formats are 'xxx_atc_2nM_yyy.trk' where 'xxx_' and '_yyy' can be
          anything. The 'nM' (or 'pM') notation must come immediatly after the kmer.
          It can be upper or lower-case names indifferently.
        * '3mer': same as 'kmer' but detects only 3mers
        * '4mer': same as 'kmer' but detects only 4mers
        * A regular expression with a group named `ol`. The latter will be used
          as the oligos.

    Returns
    -------

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
    level:               Level            = Level.peak
    fit:                 Fitters          = dict()
    constraints:         Constraints      = dict()
    match:               Matchers         = dict()
    pullphaseratio:      Optional[float]  = .88
    singlestrand:        SingleStrandTask = SingleStrandTask()
    baseline:            BaselinePeakTask = BaselinePeakTask()
    sequences:           Sequences        = None
    oligos:              Oligos           = None
    DEFAULT_FIT:         HairpinFitter    = PeakGridFit
    DEFAULT_MATCH:       PeakMatching     = PeakMatching
    DEFAULT_CONSTRAINTS: Dict[str, Range] = dict(
        stretch = Range(None, 0.1,  10.),
        bias    = Range(None, 1e-4, 3e-3)
    )

    def __delayed_init__(self, kwa):
        if 'sequence' in kwa:
            if 'sequences' in kwa:
                raise KeyError("Use either sequence or sequences as keyword")
            self.sequences = kwa['sequence']
        if not isinstance(self.fit, dict):
            self.fit   = {None: self.fit}
        if not isinstance(self.match, dict):
            self.match = {None: self.match}
        if ('sequences' in kwa or 'sequence' in kwa) and 'oligos' in kwa:
            self.__dict__.update(self.resolve(None).__dict__)

    @initdefaults(frozenset(locals()) - {'level'})
    def __init__(self, **kwa):
        super().__init__(**kwa)

    def resolve(self, path: Union[str, Path, Tuple[Union[str, Path],...]]) -> 'FitToHairpinTask':
        "create a new task using attributes sequences & oligos"
        if not self.sequences or not self.oligos:
            return self

        oligos = list(splitoligos(self.oligos, path = path))
        if len(oligos) == 0 and self.oligos:
            return self

        cpy = self.__new__(type(self))
        cpy.__dict__.update(
            self.__dict__,
            fit    = deepcopy(self.fit),
            match  = deepcopy(self.match),
            oligos = oligos,
        )
        try:
            other = self.read(cpy.sequences, cpy.oligos, fit = self.fit, match = self.match)
        except FileNotFoundError:
            return cpy

        if other:
            for left, right in ((cpy.fit, other.fit), (cpy.match, other.match)):
                left.update({i:j for i, j in right.items() if i not in left})
                for i  in set(right) & set(left):
                    right[i].peaks = left[i].peaks
        return cpy

    @classmethod
    def isslow(cls) -> bool:
        "whether this task implies long computations"
        return True

    @classmethod
    def read(
            cls,
            path:   StreamUnion,
            oligos: Sequence[str],
            fit:    Union[Fitters,  Type[HairpinFitter]] = None,
            match:  Union[Matchers, Type[PeakMatching]]  = None,
    ) -> 'FitToHairpinTask':
        "creates a BeadsByHairpin from a fasta file and a list of oligos"
        if isinstance(fit, dict):
            fit = fit.get(None, next(iter(fit.values()), None))
        if isinstance(match, dict):
            match = match.get(None, next(iter(match.values()), None))
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
    key:          BEADKEY
    silhouette:   float
    distances:    Dict[Optional[str], Distance]
    peaks:        PEAKS_TYPE
    events:       PeakListArray
    baseline:     Optional[float]
    singlestrand: Optional[float]

class FitToHairpinDict(TaskView[FitToHairpinTask, BEADKEY]):  # pylint: disable=too-many-ancestors
    "iterator over peaks grouped by beads"
    level:     Level = FitToHairpinTask.level
    config:    FitToHairpinTask
    _resolved: Union[str, Path, Tuple[Union[str, Path],...]]

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

    def distances(
            self,
            key:      BEADKEY,
            inp:      Optional[PeakListArray] = None,
            baseline: Optional[bool]          = None,
            strand:   Optional[bool]          = None,
    ) -> Dict[Optional[str], Distance]:
        "compute distances from peak data"
        if inp is None:
            inp = self.__topeaks(cast(PeakEvents, cast(dict, self.data)[key]))
        bead = inp['peaks']
        return {
            name: calc.optimize(bead)
            for name, calc in self.fits(key, inp, baseline, strand).items()
        }

    def fits(
            self,
            key:      BEADKEY,
            inp:      Optional[PeakListArray] = None,
            baseline: Optional[bool]          = None,
            strand:   Optional[bool]          = None
    ) -> Dict[Optional[str], HairpinFitter]:
        "compute distances from peak data"
        if inp is None:
            inp = self.__topeaks(cast(PeakEvents, cast(dict, self.data)[key]))

        fits = {i: j for i, j in self.config.fit.items() if len(j.peaks)}
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

        if any(i.hassinglestrand for i in fits.values()):
            strand = self.__singlestrand(key, inp) is not None if strand is None else strand

            if strand is True:
                # single-strand found: use it as a pivot
                fits.update((i, updatecopy(j, pivot = Pivot.top))
                            for i, j in fits.items() if j.hassinglestrand)
            elif strand is False:
                # single-strand found as missing: discard it from fit
                fits.update((i, updatecopy(j, peaks = j.peaks[:-1]))
                            for i, j in fits.items() if j.hassinglestrand)

        if baseline is False or self.__baseline(key, inp) is False:
            # baseline missing: don't use it as a pivot
            fits.update((i, updatecopy(j, pivot = Pivot.absolute))
                        for i, j in fits.items() if not j.hassinglestrand)

        return fits

    # pylint: disable=arguments-differ
    def compute(self, aitem: Union[BEADKEY, PeakEventsTuple]) -> FitBead:
        "Action applied to the frame"
        if getattr(self, '_resolved', None) != getattr(self.track, 'path', None):
            self.config    = self.config.resolve(self.track.path)
            self._resolved = self.track.path

        if isint(aitem):
            bead = cast(BEADKEY, aitem)
            inp  = cast(PeakEvents, cast(dict, self.data)[bead])
        else:
            bead, inp = cast(PeakEventsTuple, aitem)

        events       = self.__topeaks(inp)
        baseline     = self.__baseline(bead, inp)
        singlestrand = self.__singlestrand(bead, inp)
        dist         = self.distances(
            bead,
            events,
            baseline     is not None,
            singlestrand is not None
        )
        return self.__beadoutput(bead, events, dist, (baseline, singlestrand))

    @classmethod
    def _transform_ids(cls, sel):
        return cls._transform_to_bead_ids(sel)

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

    def __baseline(self, bead:int, peaks: PeakListArray) -> Optional[float]:
        out = (
            BaselinePeakProcessor(task = self.config.baseline)
            .index(self.data, bead, peaks)
        )
        return None if out is None else peaks[out][0]

    def __singlestrand(self, bead:int, peaks: PeakListArray) -> Optional[float]:
        out = (
            SingleStrandProcessor(task = self.config.singlestrand)
            .index(self.data, bead, peaks)
        )
        return None if out is None or out >= len(peaks) else peaks[out][0]

    def __beadoutput(
            self,
            key:    BEADKEY,
            events: PeakListArray,
            dist:   Dict[Optional[str], Distance],
            refs:   Tuple[Optional[float], Optional[float]]
    ) -> FitBead:
        if len(dist) == 0:
            return FitBead(
                key, -1., dist, PeakMatching.empty(events['peaks']), events, *refs
            )

        best = cast(str, min(dist, key = dist.__getitem__))
        silh = HairpinFitter.silhouette(dist, best)
        alg  = self.config.match.get(best, self.config.DEFAULT_MATCH())
        ids  = alg.pair(events['peaks'], *dist.get(best, (0., 1., 0))[1:])
        return FitBead(key, silh, dist, ids, events, *refs)

class FitToHairpinProcessor(TaskViewProcessor[FitToHairpinTask, FitToHairpinDict, BEADKEY]):
    "Groups beads per hairpin"
    @staticmethod
    def keywords(cnf:Dict[str, Any]) -> Dict[str, Any]:
        "changes keywords as needed"
        fit         = cnf.get('fit',         None)
        match       = cnf.get('match',       None)
        constraints = cnf.get('constraints', None)
        cnf.update(fit         = {} if not fit         else fit,  # type: ignore
                   constraints = {} if not constraints else constraints,
                   match       = {} if not match       else match)
        return cnf

@DataFrameFactory.adddoc
class FitsDataFrameFactory(DataFrameFactory[FitToHairpinDict]):
    """
    Transform a `FitToHairpinDict` to one or more `pandas.DataFrame`.

    The dataframe contains one row per bead and valid hairpin. By valid one means
    a hairpin, for a given bead, which was fitted against the latter. Some hairpins
    are considered incorrect, for example if their size is inconsistent with that
    of the bead.

    As an example, if there are 2 possible hairpins and 3 beads, there should be
    from 0 to 6 rows in the dataframe. Zero would imply that none of the beads
    had a size consistent with any of the hairpins.

    Default Indexes
    ---------------

    * track: the track from which is issued a given bead
    * bead: the bead id in the track

    Default Columns
    ---------------

    * hpin:           the hairpin name.
    * cost:           the cost value for fitting the bead to that hairpin.
      This value may vary depending on which cost function was selected and its
      configuration.
    * oligo:          the oligos used for fitting, if known.
    * stretch:        the stretch value from fitting to that hairpin.
    * bias:           the bias value from fitting to that hairpin.
    * strandsize:     the sequence length
    * nbindings:      the number of expected bindings on the hairpin.
    * nblockages:     the number of blockage positions detected on the bead.
    * hfsigma:        the high frequency noise for that bead.
    * considering blockage positions versus expected bindings:
        * expnonaffected: the number of formers not assigned to any of the latters.
        * expaffected:    the number of assigned formers including duplicated formers.
        * expfalseneg:    the number of peak(s) which not appear experimently but
          assigned theoretically.
        * exptruepos:     the number of assigned formers.
        * expresiduals:   the mean distance from a former to its assigned latter.
        * expduplicates:  the number of assigned formers less the number of assigned latters.
    * considering expected bindings versus blockage positions:
        * hpinnonaffected : the number of formers not assigned to any of thelatters.
        * hpinfalseneg:     the number of latters without assignees. => ignore, No SENSE.
        * hpinaffected :    the number of assigned formers.
        * hpinresiduals:    the mean distance from a former to its assigned latter.
        * hpinduplicates:   the number of assigned formers less the number of assigned latters.
    * For identified blockage positions:
        * tpaverageduration:   the average event duration
        * tphybridisationrate: the average event rate
        * tpeventcount:        the average event count
    * For non-identified blockage positions:
        * fpaverageduration:   the average event duration
        * fphybridisationrate: the average event rate
        * fpeventcount:        the average event count

    Configuration
    -------------

    The following can be provided to the `measures` dictionnary of the task

    * aggregator: Union[str, Callable[[Sequence[float]], float]
        the aggregator to use, `np.nanmedian` by default.
    * distances: Dict[str, float]
        A dictionnary containing:
        ```python
        {
            'bead': max distance from blockage positions to an expected binding,
            'hpin': max distance from expected bindings to a blockage position.
        }
        ```
    * peaks: Union[Bool, Dict[str, Any]]
        If `peaks = True`, then an additionnal *peaks* column is added holding
        which holds a dataframe of the peaks for a given bead and hairpin. That
        dataframe has at one row per peak and columns:
            * *peakposition*
            * *hybridisationrate*
            * *averageduration*
            * *status*: either '< baseline', 'baseline' 'falsepos', 'truepos',
            'singlestrand', '> singlestrand' as needed.
            * *baseposition*: the *peakposition* in base pairs
            * *closest*: the closest theoretical position
            * *distance*: the distance to the closest theoretical position

        If *peaks* is a dictionnary, it is passed to a PeaksDataFrameFactory.
        The latter will measure statistics on true positives and false
        positives, then report the results aggregated by bead and hairpin.
        Should the dictionnary contain `all = True`, then the previous *peaks*
        column is added.

    * optionals: Dict[str, Callable[[FitToHairpinDict, int, FitBead], np.ndarray]]
        A dictionnary for creating additional columns. The functions take 3 arguments,
        the view, the bead id, and the results for that bead.
    """
    # pylint: disable=arguments-differ
    def __init__(
            self,
            task,
            buffers,
            frame:     FitToHairpinDict,
            **kwa:     Callable[[FitToHairpinDict, int, FitBead], np.ndarray]
    ):
        super().__init__(task, buffers, frame)
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

        self.__keeppeaks = False
        if meas.get('peaks', None) is True:
            meas.pop('peaks')
            self.__keeppeaks = True
        elif meas.get('peaks', {}).get('all', False):
            self.__keeppeaks = True
        meas.get('peaks', {}).pop('all', None)

        peaks = DataFrameTask(measures = meas.pop('peaks', {}))
        self.__peaks: PeaksDataFrameFactory = (
            PeaksDataFrameFactory(peaks, buffers, frame)
            .discardcolumns('track', 'bead')
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
    ) -> Dict[str, np.ndarray]:  # type: ignore
        frame = self.__config(frame)
        fits  = frame.fits(bead, res.events)
        out   = self.__basic(frame, bead, res, fits)
        out.update(self.__complex(frame, res, fits))
        out.update({i: j(frame, bead, res) for i, j in self.__optionals.items()})

        out['oligo'] = np.empty(len(next(iter(out.values()))), dtype = f'<U{self.OSZ}')
        if isinstance(frame.config.oligos, (str, Pattern)):
            out['oligo'][:] = str(frame.config.oligos)[:self.OSZ]
        elif frame.config.oligos is not None:
            out['oligo'][:] = ','.join(str(i) for i in frame.config.oligos)[:self.OSZ]

        if fits:
            out['expfalseneg']  = out['nbindings']  - out['exptruepos']
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
                "Dataframe can only be created if a FitToHairpinTask is in the tasklist"
            )
        return cast(FitToHairpinDict, first)

    OSZ: ClassVar[int] = 30
    @staticmethod
    def __basic(
            frame: FitToHairpinDict,
            bead:  int,
            res:   FitBead,
            fits:  Dict[Optional[str], HairpinFitter]
    ) -> Dict[str, np.ndarray]:
        size = len(res.distances)
        return {
            'hpin':       np.array(list(res.distances),                    dtype = '<U20'),
            'cost':       np.array([i[0] for i in res.distances.values()], dtype = 'f4'),
            'stretch':    np.array([i[1] for i in res.distances.values()], dtype = 'f4'),
            'bias':       np.array([i[2] for i in res.distances.values()], dtype = 'f4'),
            'nbindings':  np.array([i.peaks.size for i in fits.values()],  dtype = 'i4'),
            'strandsize': np.array([i.strandsize for i in fits.values()],  dtype = 'i4'),
            'nblockages': np.full(size, len(res.events),                   dtype = 'i4'),
            'hfsigma':    np.full(size, frame.track.rawprecision(bead),    dtype = 'f4')
        }

    def __complex(
            self,
            frame: FitToHairpinTask,
            res:   FitBead,
            fits:  Dict[Optional[str], HairpinFitter],
    ) -> Dict[str, np.ndarray]:
        info: Dict[str, List[float]] = {}
        dist = res.distances
        data = self.__base_df(frame, res)
        cols = list((set(data.columns) - {'peakposition', 'status'}))
        for tpe in ('bead', 'hpin'):
            for hpin, alg in fits.items():
                window = self.__dist_complex(tpe, hpin, frame.config)
                self.__bead_hpin_complex(
                    tpe,
                    info,
                    self.__pks_complex(res, dist, hpin, alg),
                    window
                )
                if tpe != 'hpin':
                    cur = self.__peaks_df(info, res.distances[hpin], alg.peaks, window, data)
                    self.__tp_fp_complex(cols, info, cur)

        out = {i: np.array(j, dtype = 'f4') for i, j in info.items() if i != 'peaks'}
        if 'peaks' in info:
            out['peaks'] = np.full(len(next(iter(out.values()))), None, dtype = 'O')
            out['peaks'][:] = info['peaks']
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

    def __base_df(self, frame, res) -> pd.DataFrame:
        data   = pd.DataFrame(self.__peaks.dictionary(frame, (res.key, res.events)))
        status = np.full(data.shape[0], "", dtype = "<U14")
        if frame.config.baseline:
            ind = (
                BaselinePeakProcessor(task = frame.config.baseline)
                .index(frame, res.key, res.events)
            )
            if ind is not None and 0 <= ind < len(res.events['peaks']):
                pos = res.events['peaks'][ind]
                status[data.peakposition < pos]  = "< baseline"
                status[data.peakposition == pos] = "baseline"

        if frame.config.singlestrand:
            ind = (
                SingleStrandProcessor(task = frame.config.singlestrand)
                .index(frame, res.key, res.events)
            )
            if ind is not None and 0 <= ind < len(res.events['peaks']):
                pos = res.events['peaks'][ind]
                status[data.peakposition == pos] = "singlestrand"
                status[data.peakposition > pos]  = "> singlestrand"
        data['status'] = status
        return data

    def __peaks_df(   # pylint: disable=too-many-arguments
            self, out, dist, hpinpeaks, window, data
    ) -> pd.DataFrame:
        hpos = (data['peakposition'] - dist[2]) * dist[1]
        inds = np.minimum(len(hpinpeaks)-1, np.searchsorted(hpinpeaks, hpos))
        inds[
            np.abs(hpinpeaks[inds] - hpos) > np.abs(hpinpeaks[np.maximum(0, inds-1)] - hpos)
        ] -= 1

        delta  = hpinpeaks[inds] - hpos
        status = np.copy(data['status'])
        status[(status == '') & (np.abs(delta) < window)] = 'truepos'
        status[status == ''] = 'falsepos'

        data = data.assign(
            closest      = hpinpeaks[inds],
            distance     = delta,
            baseposition = hpos,
            status       = status
        )

        if self.__keeppeaks:
            out.setdefault('peaks', []).append(data)
        return data

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

        if tpe == "bead":
            tpe = "exp"
        out.setdefault(tpe+'affected',    []).append(np.array(good.sum(), dtype = 'i4'))
        out.setdefault(tpe+'nonaffected', []).append(good.size - good.sum())
        out.setdefault(tpe+'duplicates',  []).append(good.size - np.unique(ids).size)
        out.setdefault(tpe+'truepos',     []).append(np.unique(ids).size)
        out.setdefault(tpe+'residuals',   []).append(
            self.__aggregator(
                np.abs(arrs[tpe == 'exp'][ids]-arrs[tpe != 'exp'][good]) ** 2
            )
        )

    def __tp_fp_complex(  # py
            self,
            cols:   List[str],
            out:    Dict[str, List[float]],
            data:   pd.DataFrame,
    ):
        for fmt in ('tp', 'fp'):
            tmp = data.loc[
                data['status'] == ('truepos' if fmt == 'tp' else 'falsepos'),
                cols
            ]
            if tmp.shape[0]:
                for i, j in tmp.iteritems():
                    out.setdefault(fmt+i, []).append(self.__aggregator(j))
            else:
                for i, j in tmp.iteritems():
                    out.setdefault(fmt+i, []).append(np.NaN)
