#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Processors apply tasks to a data flow"
from   enum               import Enum
from   functools          import partial
from   typing             import Optional, NamedTuple # pylint: disable=unused-import

import numpy                 as     np
from   utils                 import initdefaults
from   taskmodel             import Task, Level, PHASE
from   taskcontrol.processor import Processor
from   .._core               import (# pylint: disable=import-error
    translate, medianthreshold, ExtremumAlignment, ExtremumAlignmentMode,
    PhaseEdgeAlignment, PhaseEdgeAlignmentMode
)

def _min_extension():
    try:
        from cleaning.datacleaning import ExtentRule
    except ImportError:
        from utils.logconfig import getLogger
        getLogger(__name__).warning("Could not obtain min extension from the cleaning module")
        return .25
    return ExtentRule().minextent

class AlignmentTactic(Enum):
    "possible alignments"
    onlyinitial = 'onlyinitial'
    onlypull    = 'onlypull'
    measure     = 'measure'
    initial     = 'initial'
    pull        = 'pull'

class ExtremumAlignmentTask(Task):
    """
    Task for aligning on a given phase.

    # Alignment modes are:

    * *phase* = 'onlyinitial': alignment on `PHASE.initial`
    * *phase* = 'onlypull': alignment on `PHASE.pull`
    * *phase* = 'initial': alignment is performed `PHASE.initial`. Outliers are
    then re-aligned on `PHASE.pull`. Outliers are defined as:

        * |`PHASE.pull` - median(`PHASE.pull`)| > 'pull'
        * at least one of the extension between `PHASE.initial` and 3 or 3 and 5
        are such that: (extension > median(extension) x 'opening')
        that between `PHASE.initial` and 3 or 3 and 5.

    * *phase* = 'pull': alignment is performed `PHASE.pull`. Outliers are
    then re-aligned on `PHASE.initial`. Outliers satisfy all conditions:

        * |`PHASE.pull`    - `PHASE.measure`| < 'outlier' x median
        * |`PHASE.pull`    - `PHASE.initial`| < 'outlier' x median
        * |`PHASE.initial` - `PHASE.measure`| < 'delta'

    After alignment, cycles with |phase 7| < median + 'minrelax' are discarded.

    * *phase* = 'measure': alignment is performed on `PHASE.measure`. If outliers
    are found on `PHASE.measure`:

        * if more than 'fiveratio' cycles are further than 'pull' from the
        median, a *phase* = None alignment is returned.
        * otherwise outliers are aligned on `PHASE.initial`. Finally `PHASE.pull`
        outliers are re-aligned on `PHASE.pull`.

    In any case, cycles that could not be aligned are removed.

    # Attributes:

    * *window:* The number of frames used to measure the phase position.
    This is *ExtremumAlignment.binsize* if *edge* is *False* and
    *PhaseEdgeAlignment.window* if *edge* is *True*.
    * *edge:* Whether to look at the extremum etremorum (ExtremumAlignment) or
    simply to align on a given side (EdgeAlignment).
    * *phase:* Whether to align a specific phase or on the best.
    * *opening:* This factor is used to determine cycles mis-aligned on *phase*.
    * *pull:* maximum absolute distance from the median `PHASE.pull` value.
    """
    level      = Level.bead
    window     = 15
    edge       = 'right' # type: Optional[str]
    phase      = AlignmentTactic.pull  # type: AlignmentTactic
    percentile = 25.
    fiveratio  = .4
    outlier    = .9
    pull       = .1
    opening    = _min_extension()
    delta      = .2
    minrelax   = .1
    delete     = True

    @initdefaults(frozenset(locals()) - {'level'})
    def __init__(self, **_):
        super().__init__()

class ExtremumAlignmentProcessor(Processor[ExtremumAlignmentTask]):
    "Aligns cycles to zero"
    class _Utils:
        "Aligns cycles to zero"
        def __init__(self, frame, info):
            "returns computed cycles for this bead"
            self.frame = frame
            self.info  = info
            self.bead  = self.info[1]
            if self.frame.cycles and self.frame.cycles.stop < self.frame.track.ncycles:
                self.bead = self.bead[:self.frame.track.phase.select(self.frame.cycles.stop, 0)]

        def phase(self, phase):
            "return the phases"
            cyc = self.frame.cycles
            out = self.frame.track.phase.select(cyc if cyc else ..., phase)
            assert out.dtype == np.dtype("i4"), f'{out.dtype}'
            return out

        def bias(self, phase, window, edge, percentile):
            "aligns a phase"
            if edge is not None:
                mode  = (PhaseEdgeAlignmentMode.left if edge == 'left' else
                         PhaseEdgeAlignmentMode.right)
                align = PhaseEdgeAlignment(window     = window,
                                           mode       = mode,
                                           percentile = percentile)
            else:
                mode  = (ExtremumAlignmentMode.min if phase == PHASE.pull else
                         ExtremumAlignmentMode.max)
                align = ExtremumAlignment(binsize = window, mode = mode)
            return align.compute(self.bead, self.phase(phase), self.phase(phase+1))

        def translate(self, delete, bias):
            "translates data according to provided biases"
            translate(delete, bias, self.phase(0), self.bead)
            return self.info

    _Args = NamedTuple('_Args',
                       [('cycles',  _Utils),
                        ('initial', np.ndarray),
                        ('pull',    np.ndarray),
                        ('measure', Optional[np.ndarray])])

    @classmethod
    def _get(cls, kwa:dict, name:str):
        return kwa.get(name, getattr(cls.tasktype, name))

    @classmethod
    def _apply_initial(cls, kwa, frame, info):
        args = cls.__args(kwa, frame, info, False)
        return cls.__align_on_3('initial', args.initial, args, kwa)

    @classmethod
    def _apply_pull(cls, kwa, frame, info):
        args  = cls.__args(kwa, frame, info, True)
        delta = args.initial-args.pull
        if not np.any(np.isfinite(delta)):
            return args.cycles.info

        bias = args.pull + np.nanpercentile(delta, 100.-cls._get(kwa, 'percentile'))
        bad  = cls.__less(args.measure-args.pull, kwa, 'opening')
        bad &= cls.__less(args.initial-args.pull, kwa, 'opening')
        bad |= np.isnan(bias)
        if any(bad):
            bad = np.nonzero(bad)[0]
            bad = bad[cls.__less(args.initial[bad]-args.measure[bad], kwa, 'delta')]
            if len(bad):
                bias[bad] = args.initial[bad]

        cls.__filter_on_relax(args, kwa, bias)
        return args.cycles.translate(cls._get(kwa, 'delete'), bias)

    @classmethod
    def _apply_measure(cls, kwa, frame, info):
        args = cls.__args(kwa, frame, info, True)
        bias = args.measure

        dtl5 = cls.__deltas('measure', 'outlier', args, kwa)
        bad  = dtl5 < 1.
        if any(bad):
            tmp = cls.__distance_to_3(bias, args, kwa)
            if (tmp > 1).sum() > (tmp >= 0).sum() * cls._get(kwa, 'fiveratio'):
                # too many cycles are saturated
                return cls.__align_on_3('initial', args.initial, args, kwa)

            bad       = np.logical_and(bad, cls.__deltas('initial', 'outlier', args, kwa) >= 1.)
            bias      = np.copy(bias)
            bias[bad] = args.initial[bad]+np.nanmedian(args.measure-args.initial)

        return cls.__align_on_3('measure', bias, args, kwa)

    @classmethod
    def _apply_onlyinitial(cls, kwa, frame, info):
        args = cls.__args(kwa, frame, info, False)
        return args.cycles.translate(cls._get(kwa, 'delete'), args.initial)

    @classmethod
    def _apply_onlypull(cls, kwa, frame, info):
        args = cls.__args(kwa, frame, info, False)
        bias = args.pull + np.nanmedian(args.initial-args.pull)
        return args.cycles.translate(cls._get(kwa, 'delete'), bias)

    @classmethod
    def __args(cls, kwa, frame, info, meas) -> 'ExtremumAlignmentProcessor._Args':
        cycles     = cls._Utils(frame, info)
        window     = cls._get(kwa, 'window')
        edge       = cls._get(kwa, 'edge')
        percentile = cls._get(kwa, 'percentile')

        inits = cycles.bias(PHASE.initial, window, edge,      percentile) # ≈ min
        pulls = cycles.bias(PHASE.pull,    window, edge, 100.-percentile) # ≈ max
        if meas:
            return cls._Args(cycles, inits, pulls,
                             cycles.bias(PHASE.measure, window, 'right', percentile))

        return cls._Args(cycles, inits, pulls, None)

    @classmethod
    def __deltas(cls, attr:str, outlier: str, args:_Args, kwa):
        arr = getattr(args, attr)
        if arr is None:
            edge = 'right' if attr == 'measure' else cls._get(kwa, 'edge')
            wind = cls._get(kwa, 'window')
            perc = cls._get(kwa, 'percentile')
            if attr == 'pull':
                perc = 100. - perc
            arr  = args.cycles.bias(getattr(PHASE, attr), wind, edge, perc)

        deltas = arr - args.pull
        rho    = np.nanmedian(deltas)*cls._get(kwa, outlier)
        if rho <= 0.:
            deltas[:] = 2.
        else:
            deltas /= rho
            deltas[np.isnan(deltas)] = 0.
        return deltas

    @classmethod
    def __filter_on_relax(cls, args, kwa, bias):
        minv =  cls._get(kwa, 'minrelax')
        if minv is not None:
            medianthreshold(minv, args.cycles.bead,
                            args.cycles.phase(PHASE.relax),
                            args.cycles.phase(PHASE.relax+1),
                            bias)

    @classmethod
    def __less(cls, array, kwa, name):
        val                    =  cls._get(kwa, name)
        array[np.isnan(array)] = val
        return array < val

    @classmethod
    def __distance_to_3(cls, bias, args, kwa):
        tmp  = bias-args.pull
        tmp -= np.nanmedian(tmp)
        tmp /= cls._get(kwa, 'pull')
        np.abs(tmp, tmp)
        tmp[np.isnan(tmp)] = -1.
        return tmp

    @classmethod
    def __align_on_3(cls, attr, bias, args, kwa):
        tmp = cls.__distance_to_3(bias, args, kwa) > 1.
        if any(tmp):
            bad  = np.logical_or(cls.__deltas('initial', 'opening', args, kwa) >= 1.,
                                 cls.__deltas('measure', 'opening', args, kwa) >= 1.)

            np.logical_and(bad, tmp, bad)
            bias[bad] = args.pull[bad]+np.nanmedian(getattr(args, attr)-args.pull)
        return args.cycles.translate(cls._get(kwa, 'delete'), bias)

    @classmethod
    def apply(cls, toframe = None, **kwa):
        "applies the task to a frame or returns a function that does so"
        assert cls._get(kwa, 'percentile') <= 50.
        mode   = cls._get(kwa, 'phase')
        action = getattr(cls, '_apply_'+mode.name)

        def _apply(frame):
            return frame.withaction(partial(action, kwa))
        return _apply if toframe is None else _apply(toframe)

    def run(self, args):
        "updates frames"
        args.apply(self.apply(**self.config()))
