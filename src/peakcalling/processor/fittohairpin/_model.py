#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Matching experimental peaks to hairpins: tasks and processors"
from   copy                        import deepcopy
from   pathlib                     import Path
from   typing                      import (
    Dict, Sequence, NamedTuple, List, Type, Tuple, Union, Optional, Iterable, Pattern, cast
)

import numpy                       as     np

from   peakfinding.peaksarray      import Output as PeakFindingOutput, PeakListArray
from   peakfinding.processor       import PeaksDict, SingleStrandTask, BaselinePeakTask
from   sequences                   import splitoligos, read as _read
from   taskmodel                   import Task, Level
from   utils.logconfig             import getLogger
from   utils                       import (
    StreamUnion, initdefaults, updatecopy, DefaultValue
)
from   ...tohairpin                import (
    HairpinFitter, PeakGridFit, Distance, PeakMatching, PEAKS_TYPE
)
from   ..._base                    import Range

LOGS = getLogger("__name__")

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
Constraints = Dict[int, DistanceConstraint]
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
        if (
                not self.sequences
                or not self.oligos
                or len(self.fit) > 1
                or (set(self.fit) - {None})
        ):
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
        except FileNotFoundError as exc:
            LOGS.warning("%s", exc)
            return cpy

        if other:
            for left, right in ((cpy.fit, other.fit), (cpy.match, other.match)):
                left.update({i:j for i, j in right.items() if i not in left})
                for i  in set(right) & set(left):
                    right[i].peaks = left[i].peaks
            cpy.sequences = other.sequences
            cpy.oligos    = other.oligos
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

        return cls(
            fit   = fits,
            match = {
                key: updatecopy(
                    imatch, True,
                    peaks      = value.peaks,
                    strandsize = value.strandsize
                )
                for key, value in fits.items()
            },
            oligos    = oligos,
            sequences = (
                dict(_read(path)) if isinstance(path, (dict, str, Path)) else
                None
            )
        )


PeakEvents      = Iterable[PeakFindingOutput]
PeakEventsTuple = Tuple[int, PeakEvents]
_PEAKS          = Tuple[np.ndarray, PeakListArray]
Input           = Union[PeaksDict, PeakEvents]

class FitBead(NamedTuple):
    key:          int
    silhouette:   float
    distances:    Dict[Optional[str], Distance]
    peaks:        PEAKS_TYPE
    events:       PeakListArray
    baseline:     Optional[float]
    singlestrand: Optional[float]
