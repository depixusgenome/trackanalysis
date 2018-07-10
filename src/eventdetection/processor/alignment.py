#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Processors apply tasks to a data flow"
import warnings
from   typing             import Optional, NamedTuple # pylint: disable=unused-import
from   functools          import partial
from   enum               import Enum

import numpy              as     np
from   utils              import initdefaults, updatecopy
from   model              import Task, Level, PHASE
from   control.processor  import Processor
from   ..alignment        import ExtremumAlignment, PhaseEdgeAlignment

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
            self.cycles = frame.track.view('cycles', data = {info[0]: info[1]})
            if frame.cycles is not None:
                phases            = frame.track.phases[frame.cycles,:]
                self.cycles.track = updatecopy(frame.track, phases = phases)

        def values(self, phase):
            "aligns a phase"
            return self.cycles.withphases(phase).values()

        def bias(self, phase, window, edge, percentile):
            "aligns a phase"
            vals  = np.array(list(self.values(phase)), dtype = 'O')
            if edge is not None:
                align = PhaseEdgeAlignment(window     = window,
                                           edge       = edge,
                                           percentile = percentile)
            else:
                mode  = 'min'  if phase == PHASE.pull else 'max'
                align = ExtremumAlignment(binsize = window, mode = mode).many
            return align(vals, subtract = False)

        def translate(self, delete, bias):
            "translates data according to provided biases"
            for val, delta in zip(self.values(...), bias):
                if np.isfinite(delta):
                    val += delta
                elif delete:
                    val[:] = np.NaN

            return next(iter(self.cycles.data.items()))

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
        args = cls.__args(kwa, frame, info, True)
        bias = args.pull + np.nanpercentile(args.initial-args.pull,
                                            100.-cls._get(kwa, 'percentile'))

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
        if minv is None:
            return

        vals = list(args.cycles.values(PHASE.relax))
        with warnings.catch_warnings():
            warnings.filterwarnings('ignore', category = RuntimeWarning,
                                    message = '.*All-NaN slice encountered.*')
            relax = np.array([np.nanmedian(i) for i in vals], dtype = 'f4') + bias

            warnings.filterwarnings('ignore', category = RuntimeWarning,
                                    message = '.*invalid value encountered in less.*')
            bias[relax < np.nanmedian(relax)-minv] = np.NaN

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
