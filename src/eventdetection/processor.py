#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Processors apply tasks to a data flow"
from   typing             import Optional, NamedTuple # pylint: disable=unused-import
from   functools          import partial

import numpy              as     np
from   utils              import initdefaults, updatecopy
from   model              import Task, Level, PHASE
from   control.processor  import Processor

from   .data              import Events
from   .alignment         import ExtremumAlignment, PhaseEdgeAlignment
from   .                  import EventDetectionConfig

class ExtremumAlignmentTask(Task):
    """
    Task for aligning on a given phase.

    Alignment is performed on *phase* for all then only on outliers using
    either phase 3, if *phase* is 1, or phase 1 if *phase* is 5. This is done
    the following way:

        1. Algnments are performed on *phase*.
        2. The extension between phases 3 and 1 and 3 and 5 are computed.
        3. Cycles are considered miss-aligned only if the bead opened during that
        cycle. The test is:

            * *phase* to phase 3 extension < median x outlier
            * 3-5 extension                > median x outlier

        4. Mis-aligned cycles are aligned to the median value of *aligned* values
        of the outlier phase.

    Finally, if *phase* is 5, cycles with the following property are aligned on phase 3:

            * |phase 3 - median| > pull
            * (3-5 extension > median x opening) or (1-5 extension > median x opening)

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
    level     = Level.bead
    window    = 15
    edge      = 'right' # type: Optional[str]
    phase     = None    # type: Optional[int]
    outlier   = .9
    pull      = .1
    opening   = .5

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

        def bias(self, phase, window, edge):
            "aligns a phase"
            vals  = np.array(list(self.cycles.withphases(phase).values()), dtype = 'O')
            if edge is not None:
                align = PhaseEdgeAlignment(window = window, edge = edge)
            else:
                mode  = 'min'  if phase == PHASE.pull else 'max'
                # pylint: disable=redefined-variable-type
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
    def apply(cls, toframe = None, **kwa):
        "applies the task to a frame or returns a function that does so"
        action = (cls.__apply_best13 if cls._get(kwa, 'phase') is None          else
                  cls.__apply_best51 if cls._get(kwa, 'phase') == PHASE.measure else
                  cls.__apply_onephase)

        def _apply(frame):
            return frame.withaction(partial(action, kwa, frame),
                                    beadsonly = True)
        return _apply if toframe is None else _apply(toframe)

    @classmethod
    def __args(cls, kwa, frame, info, meas) -> 'ExtremumAlignmentProcessor._Args':
        cycles  = cls._Utils(frame, info)
        window  = cls._get(kwa, 'window')
        edge    = cls._get(kwa, 'edge')
        inits   = cycles.bias(PHASE.initial, window, edge)
        pulls   = cycles.bias(PHASE.pull, window, edge)
        if meas:
            return cls._Args(cycles, inits, pulls,
                             cycles.bias(PHASE.measure, window, 'right'))

        else:
            return cls._Args(cycles, inits, pulls, None)

    @classmethod
    def __deltas(cls, attr:str, outlier: str, args:_Args, kwa):
        arr = getattr(args, attr)
        if arr is None:
            edge = 'right' if attr == 'measure' else cls._get(kwa, 'edge')
            wind = cls._get(kwa, 'window')
            arr  = args.cycles.bias(getattr(PHASE, attr), wind, edge)

        deltas = arr - args.pull
        rho    = np.nanmedian(deltas)*cls._get(kwa, outlier)
        if rho <= 0.:
            deltas[:] = 2.
        else:
            deltas /= rho
            deltas[np.isnan(deltas)] = 0.
        return deltas

    @classmethod
    def __align_on_3(cls, bias, args, kwa):
        tmp  = bias-args.pull
        tmp -= np.nanmedian(tmp)
        tmp /= cls._get(kwa, 'pull')
        tmp[np.isnan(tmp)] = 0.

        tmp  = np.abs(tmp) > 1.
        if any(tmp):
            bad  = np.logical_or(cls.__deltas('initial', 'opening', args, kwa) >= 1.,
                                 cls.__deltas('measure', 'opening', args, kwa) >= 1.)

            np.logical_and(bad, tmp, bad)
            bias[bad] = args.pull[bad]+np.nanmedian(args.measure-args.pull)
        return args.cycles.translate(bias)

    @classmethod
    def __apply_best51(cls, kwa, frame, info):
        args = cls.__args(kwa, frame, info, True)
        bias = args.measure

        dtl5 = cls.__deltas('measure', 'outlier', args, kwa)
        bad  = dtl5 < 1.
        if any(bad):
            bad       = np.logical_and(bad, cls.__deltas('initial', 'outlier', args, kwa) >= 1.)
            bias[bad] = args.initial[bad]+np.nanmedian(args.measure-args.initial)

        return cls.__align_on_3(bias, args, kwa)

    @classmethod
    def __apply_best13(cls, kwa, frame, info):
        args = cls.__args(kwa, frame, info, False)
        bias = args.initial

        bad  = cls.__deltas('initial', 'outlier', args, kwa) < 1.
        if any(bad):
            bad       = np.logical_and(bad, cls.__deltas('measure', 'outlier', args, kwa) >= 1.)
            bias[bad] = args.pull[bad]+np.nanmedian(args.initial-args.pull)
        return args.cycles.translate(bias)

    @classmethod
    def __apply_onephase(cls, kwa, frame, info):
        window = cls._get(kwa, 'window')
        edge   = cls._get(kwa, 'edge')
        cycles = cls._Utils(frame, info)

        bias   = cycles.bias(PHASE.initial, window, edge)

        if cls._get(kwa, 'phase') == PHASE.pull:
            init  = bias
            bias  = cycles.bias(PHASE.pull, window, edge)
            bias -= np.nanmedian(bias+init)

        return cycles.translate(bias)

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
