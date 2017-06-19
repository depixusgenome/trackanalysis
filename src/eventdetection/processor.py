#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Processors apply tasks to a data flow"
from   typing             import Optional, NamedTuple # pylint: disable=unused-import
from   functools          import partial
from   enum               import Enum

import numpy              as     np
from   utils              import initdefaults, updatecopy
from   model              import Task, Level, PHASE
from   control.processor  import Processor

from   .data              import Events
from   .alignment         import ExtremumAlignment, PhaseEdgeAlignment
from   .                  import EventDetectionConfig

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

    Alignment modes are:

        * *phase* = 'onlyinitial': alignment on phase 1
        * *phase* = 'onlypull': alignment on phase 3
        * *phase* = 'initial': alignment is performed phase 1. Outliers are
        then re-aligned on phase 3. Outliers are defined as:

            * |phase 3 - median(phase 3)| > 'pull'
            * at least one of the extension between phase 1 and 3 or 3 and 5
            are such that: (extension > median(extension) x 'opening')
            that between phase 1 and 3 or 3 and 5.

        * *phase* = 'pull': alignment is performed phase 3. Outliers are
        then re-aligned on phase 1. Outliers satisfy all conditions:

            * |phase 3 - phase 5| < 'outlier' x median
            * |phase 3 - phase 1| < 'outlier' x median
            * |phase 1 - phase 5| < 'delta'
            * std(phase 3)        < 'deviation'

        * *phase* = 'measure': alignment is performed on phase 5. If outliers
        are found on phase 5:

            * if more than 'fiveratio' cycles are further than 'pull' from the
            median, a *phase* = None alignment is returned.
            * otherwise outliers are aligned on phase 1. Finally phase 3
            outliers are re-aligned on phase 3.

    Attributes:

        * *window:* The number of frames used to measure the phase position.
        This is *ExtremumAlignment.binsize* if *edge* is *False* and
        *PhaseEdgeAlignment.window* if *edge* is *True*.
        * *edge:* Whether to look at the extremum etremorum (ExtremumAlignment) or
        simply to align on a given side (EdgeAlignment).
        * *phase:* Whether to align a specific phase or on the best.
        * *opening:* This factor is used to determine cycles mis-aligned on *phase*.
        * *pull:* maximum absolute distance from the median phase 3 value.
    """
    level      = Level.bead
    window     = 15
    edge       = 'right' # type: Optional[str]
    phase      = AlignmentTactic.pull  # type: AlignmentTactic
    percentile = 25.
    fiveratio  = .4
    outlier    = .9
    pull       = .1
    opening    = .5
    delta      = .2
    deviation  = .1

    @initdefaults(frozenset(locals()) - {'level'})
    def __init__(self, **_):
        super().__init__()

class ExtremumAlignmentProcessor(Processor):
    "Aligns cycles to zero"
    class _Utils:
        "Aligns cycles to zero"
        def __init__(self, frame, info):
            "returns computed cycles for this bead"
            self.cycles = frame[info[0],...].withdata({info[0]: info[1]})
            if frame.cycles is not None:
                phases            = frame.track.phases[frame.cycles,:]
                self.cycles.track = updatecopy(frame.track, phases = phases)

        def bias(self, phase, window, edge, percentile):
            "aligns a phase"
            vals  = np.array(list(self.cycles.withphases(phase).values()), dtype = 'O')
            if edge is not None:
                align = PhaseEdgeAlignment(window     = window,
                                           edge       = edge,
                                           percentile = percentile)
            else:
                mode  = 'min'  if phase == PHASE.pull else 'max'
                align = ExtremumAlignment(binsize = window, mode = mode).many
            return align(vals, subtract = False)

        def translate(self, bias):
            "translates data according to provided biases"
            for val, delta in zip(self.cycles.withphases(...).values(), bias):
                if np.isfinite(delta):
                    val += delta
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
        bias = args.pull + np.nanmedian(args.initial-args.pull)

        bad  = args.measure-args.pull < cls._get(kwa, 'opening')
        bad &= args.initial-args.pull < cls._get(kwa, 'opening')
        if any(bad):
            bad = np.nonzero(bad)[0]
            bad = bad[np.abs(args.initial[bad]-args.measure[bad]) < cls._get(kwa, 'delta')]
            if len(bad):
                cyc = args.cycles.cycles.withphases(PHASE.measure)[..., list(bad)].values()
                std = np.array([np.nanstd(i[cls._get(kwa, 'window'):]) for i in cyc])
                bad = bad[std < cls._get(kwa, 'deviation')]
                if len(bad):
                    bias[bad] = args.initial[bad]

        return args.cycles.translate(bias)

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
        return args.cycles.translate(args.initial)

    @classmethod
    def _apply_onlypull(cls, kwa, frame, info):
        args = cls.__args(kwa, frame, info, False)
        bias = args.pull + np.nanmedian(args.initial-args.pull)
        return args.cycles.translate(bias)

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
        return args.cycles.translate(bias)

    @classmethod
    def apply(cls, toframe = None, **kwa):
        "applies the task to a frame or returns a function that does so"
        assert cls._get(kwa, 'percentile') <= 50.
        mode   = cls._get(kwa, 'phase')
        action = getattr(cls, '_apply_'+mode.value)

        def _apply(frame):
            return frame.withaction(partial(action, kwa, frame),
                                    beadsonly = True)
        return _apply if toframe is None else _apply(toframe)

    def run(self, args):
        args.apply(self.apply(**self.config()))

class EventDetectionTask(EventDetectionConfig, Task):
    "Config for an event detection"
    levelin = Level.bead
    levelou = Level.event
    phase   = PHASE.measure
    @initdefaults('phase')
    def __init__(self, **kw) -> None:
        EventDetectionConfig.__init__(self, **kw)
        Task.__init__(self)

class EventDetectionProcessor(Processor):
    "Generates output from a _tasks."
    @classmethod
    def apply(cls, toframe, **kwa):
        "applies the task to a frame or returns a function that does so"
        kwa['first'] = kwa['last'] = kwa.pop('phase')
        fcn = lambda frame: frame.new(Events, **kwa)
        return fcn if toframe is None else fcn(toframe)

    def run(self, args):
        "iterates through beads and yields cycle events"
        args.apply(self.apply(None, **self.task.config()), levels = self.levels)
