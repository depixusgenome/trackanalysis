#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Simulates binding events"
from copy   import copy
from enum   import Enum
from typing import (Dict, Any, FrozenSet, Optional, List,
                    Union, Iterable, Sequence, NamedTuple, cast)

import numpy  as np

RAND_STATE = Union[int, None, np.random.RandomState]
def randstate(seed: RAND_STATE = 0) -> np.random.RandomState:
    "return a random state"
    return seed if isinstance(seed, np.random.RandomState) else np.random.RandomState(seed)

class Object:
    """
    Auto-initialized object
    """
    _ARGS: FrozenSet[str] = frozenset()
    @staticmethod
    def args(locs)-> FrozenSet[str]:
        """
        Return current attributes
        """
        return frozenset([i for i in locs if i[0] not in ('_', i[0].upper())])

    def __init__(self, **args):
        for i in self._ARGS & set(args):
            setattr(self, i, args[i])
        for i in self._ARGS - set(args):
            setattr(self, i, copy(getattr(self.__class__, i)))

class Phase(Object):
    """
    Phase names in a cycle. Labeled phases are characterized by a stable magnet
    height.  Each of them is preceeded and followed by a phase where the magnet
    height is changed.

    The following describes the usual situation:

    * `initial`: phase 1 should be at the same magnet height (~10 pN of force) as
    `measure`. It could be used as a reference point.
    * `pull`: phase 3 is when the magnet is at the closest from the
    sample (18 pN of force). This is when a hairpin should unzip.
    * `measure`: phase 5 is when hybridisation events are measured (10 pN of force).
    * `relax`: phase 7 is used to remove probes from the hairpin.  The magnet
    is then at its farthest point (5 pN of force).
    """
    toinitial= 0
    initial  = 1
    rampup   = 2
    pull     = 3
    rampdown = 4
    measure  = 5
    torelax  = 6
    relax    = 7
    count    = 8
    _ARGS    = Object.args(locals())

class Nature(Enum):
    """
    The nature of a binding
    """
    probe        = 'probe'
    structural   = 'structural'
    singlestrand = 'singlestrand'
    spurious     = 'spurious'

class Binding(Object):
    """
    A binding's characteristics
    """
    position: float
    nature          = Nature.probe
    onrate  : float = 1.
    offrate : float = 0.
    _ARGS  = Object.args(set(locals()) | {'position'})
    def __init__(self, position, **kwa):
        super().__init__(position = position, **kwa)

class ThermalDrift:
    """
    Add thermal drift to each cycle
    """
    tscale = 30.
    zscale = 1e-2
    def __call__(self, cnf:'Experiment', bead, _ = None):
        if None in (self.tscale, self.zscale):
            return
        inds = cnf.phaseindexes('rampup', 'rampdown', 'torelax', 'count')
        size = inds[1]-inds[0]

        driftup    = np.exp((np.arange(size)-size+1)/self.tscale)
        driftup   -= driftup[0]
        driftup   *= self.zscale/driftup[-1]

        driftdown  = np.exp(-np.arange(inds[2]-inds[1])/self.tscale)
        driftdown -= driftdown[-1]
        driftdown *= driftup[-1]/driftdown[0]

        drift                   = np.zeros(inds[-1], dtype = 'f4')
        drift[inds[0]:inds[1]] += driftup
        drift[inds[1]:inds[2]] += driftdown

        if bead is not None:
            bead[:].reshape((-1, drift.size))[:] += drift
        return drift

class Baseline:
    """
    Add baseline to bead
    """
    sigma = 5e-3
    knee  = 30./1e3
    alpha = 1.
    def __call__(self, cnf: 'Experiment', seed = None):
        size    = cnf.ncycles * np.sum(cnf.phases)
        #generate white noise in time domain
        #shaping in freq domain
        fft     = getattr(np, 'fft')
        signal  = fft.rfft(randstate(seed).normal(0., self.sigma, size))
        tmp     = fft.fftfreq(size, d=1.)[:len(signal)]
        tmp[-1] = np.abs(tmp[-1])

        # set mean to 0.
        signal[0]     = 0.

        good          = np.logical_and(tmp < self.knee, tmp != 0.)
        signal[good] *= np.abs((tmp[good]/self.knee)**(-self.alpha))

        # discard high-freq amplitudes
        signal[tmp>self.knee]  = 0.
        return fft.irfft(signal)

class StrandClosingTruth(NamedTuple): # pylint: disable=missing-docstring
    duration: np.ndarray
    delta:    np.ndarray

class StrandClosing(Object):
    """
    Add a closing of the strand in phase 4
    """
    start = 40
    mean  = 3
    def __call__(self,
                 cnf: 'Experiment',
                 base: np.ndarray,
                 seed: RAND_STATE = None) -> StrandClosingTruth:
        rnd    = randstate(seed)
        inds   = cnf.phaseindexes('rampdown', 'measure')
        frames = self.start + np.int32(rnd.poisson(self.mean, cnf.ncycles))+inds[0]

        delta  = base[:,inds[1]]-base[:,inds[1]-1]
        delta -= (base[:,inds[1]-1]-base[:,inds[0]])/(inds[1]-1-inds[0])

        # make sure that no closing occurs for single strand events
        frames[delta > -5e-6] = inds[1]

        # sanity check
        frames = np.clip(frames, inds[0], inds[1])

        # deltas for non closing cycles
        delta[frames == inds[1]] = 0.

        for i, j, k in zip(frames, delta, base):
            k[i:inds[1]] += j
        return StrandClosingTruth(frames, delta)

class BrownianMotion(Object):
    "Deals with brownian motion"
    sigma: Optional[float] = 2.e-3
    pullfactor             = .8
    relaxfactor            = 1.6
    walk                   = False
    _ARGS                  = Object.args(locals())
    def __init__(self, sigma: float = None, **kwa) -> None:
        super().__init__(**kwa, **({'sigma': sigma} if sigma is not None else {}))

    def phasesigma(self, val)-> float:
        "phase 3 extension"
        return  (self.sigma*self.pullfactor  if val == 3            else
                 self.sigma*self.relaxfactor if val == 0 or val > 6 else
                 self.sigma)

    def __call__(self,
                 cnf   : 'Experiment',
                 events: np.ndarray,
                 seed  : RAND_STATE = None) -> np.ndarray:
        """
        Add brownian motion
        """
        if not self.sigma:
            return

        noise = randstate(seed).normal
        if len(events.shape) == 1 or events.shape[1] == len(cnf.bindings):
            brown = noise(0., self.sigma, events.shape)
        else:
            brown   = np.zeros(events.shape, dtype = 'f4')
            inds    = cnf.phaseindexes('initial', 'pull', 'measure', 'relax', 'count')
            size    = cnf.ncycles

            brown[:,:inds[0]]        += noise(0., self.phasesigma(7), (size, inds[0]))
            brown[:,inds[0]:inds[1]] += noise(0., self.phasesigma(1), (size, inds[1]-inds[0]))
            brown[:,inds[1]:inds[2]] += noise(0., self.phasesigma(3), (size, inds[2]-inds[1]))
            brown[:,inds[2]:inds[3]] += noise(0., self.phasesigma(5), (size, inds[3]-inds[2]))
            brown[:,inds[3]:]        += noise(0., self.phasesigma(7), (size, inds[4]-inds[3]))

        if self.walk:
            brown = np.cumsum(brown, axis = 1)
        events += brown

class _RateDescriptor:
    __slots__ = ('name',)
    def __init__(self):
        self.name = None

    def __set_name__(self, _, name):
        self.name = name[:-1]

    def __get__(self, inst, owner):
        name = self.name
        return tuple(getattr(owner, name) if inst is None else
                     (getattr(i, name) for i in inst.bindings))

    def __set__(self, inst, val):
        if np.isscalar(val):
            val = np.full(len(inst.bindings), val, dtype = 'f4')
        name = self.name
        for bind, itm in zip(inst.bindings, val):
            setattr(bind, name, itm)

class _BehaviourDescriptor:
    __slots__ = ('name', 'default')
    def __init__(self, default: type) -> None:
        self.name    = None
        self.default = default
        assert isinstance(default, type)

    def __set_name__(self, _, name):
        self.name = name

    def __get__(self, inst, owner):
        return self.default if inst is None else  inst.__dict__[self.name]

    def __set__(self, inst, val):
        # pylint: disable=not-callable
        inst.__dict__[self.name] = (self.default()      if val is True           else
                                    self.default(val)   if np.isscalar(val)      else
                                    self.default(**val) if isinstance(val, dict) else
                                    val()               if isinstance(val, type) else
                                    val)

class _BindingsDescriptor:
    def __init__(self, default: Iterable[Union[float, Binding]]) -> None:
        self.name    = None
        self.default = list(default)

    def __set_name__(self, _, name):
        self.name = name

    def __get__(self, inst, owner):
        return self.default if inst is None else  inst.__dict__[self.name]

    @staticmethod
    def create(val: Union[Binding, Dict[str, Any], float]) -> Binding:
        "return a binding"
        return (Binding(val) if np.isscalar(val)         else
                val          if isinstance(val, Binding) else
                Binding(**cast(dict, val)))

    def __set__(self, inst, val: Iterable[Union[Binding, Dict[str, Any], float]]):
        inst.__dict__[self.name] = [self.create(i) for i in val]

class BeadTruth(NamedTuple): # pylint: disable=missing-docstring
    strandclosing: Optional[StrandClosingTruth]
    events:        np.ndarray
    baseline:      Optional[np.ndarray]
    drift:         Optional[np.ndarray]

class Experiment(Object):
    """
    Information on the experiment

    # Attributes

    * *ncycles*: number of cycles

    * *durartion*: max duration of phase 5
    """
    ncycles                = 100
    bindings               = cast(List[Binding], _BindingsDescriptor([1., .8, .5, .2, .1]))
    extensionfactor        = 1.1
    phases                 = [5, 20, 5, 20, 60, 400, 5, 20]
    protocol               = Phase()
    brownianmotion         = cast(BrownianMotion, _BehaviourDescriptor(BrownianMotion))
    baseline               = cast(Baseline,       _BehaviourDescriptor(Baseline))
    thermaldrift           = cast(ThermalDrift,   _BehaviourDescriptor(ThermalDrift))
    strandclosing          = cast(StrandClosing,  _BehaviourDescriptor(StrandClosing))
    _ARGS                  = Object.args(locals())

    onrates                = cast(Sequence[Optional[float]], _RateDescriptor())
    offrates               = cast(Sequence[Optional[float]], _RateDescriptor())
    positions              = cast(Sequence[float],           _RateDescriptor())
    def __init__(self, **kwa):
        super().__init__(**kwa)
        for i in ('positions', 'onrates', 'offrates'):
            if i in kwa:
                setattr(self, i, kwa[i])

    def setup(self, **kwa):
        "reset *all* attributes"
        self.__init__(**kwa)

    def phaseindexes(self, *names) -> np.ndarray:
        "return the phase indexes from phase 0"
        inds = np.cumsum(np.insert(self.phases, 0, 0))
        if len(names) == 0:
            return inds
        prot = self.protocol.__dict__
        return inds[[prot[i] for i in names]]

    def phasez(self, val)-> float:
        "phase 3 extension"
        if val == 1:
            return 0.
        if val == 3:
            return self.singlestrandbinding.position*self.extensionfactor
        if val == 4:
            return self.singlestrandbinding.position
        return -.1

    @property
    def duration(self)-> int:
        "phase 5 duration"
        return self.phases[5]

    @property
    def singlestrandbinding(self):
        "return the single strand binding"
        val = next((i for i in self.bindings if i.nature == Nature.singlestrand),
                   None)
        if val is None:
            return Binding(max(self.positions),
                           onrate   = 0.,
                           offrate  = 0.,
                           nature   = Nature.singlestrand)
        return val

    @singlestrandbinding.setter
    def singlestrandbinding(self, value):
        "set the single strand binding"
        val = _BindingsDescriptor.create(value)
        ind = next((i for i, j in enumerate(self.bindings) if j.nature == Nature.singlestrand),
                   None)
        if ind is not None:
            self.bindings += [val]
        else:
            self.bindings[ind] = val

    @property
    def nature(self) -> np.ndarray:
        """
        Return nature of bindings
        """
        return [i.nature for i in self.bindings]

def poissonevents(cnf: Experiment, seed: RAND_STATE = None) -> np.ndarray:
    """
    Creates events using provided positions, rates and durations.
    """
    rnd   = randstate(seed)
    shape = (cnf.ncycles, len(cnf.positions))
    ron   = rnd.rand(*shape) < cnf.onrates

    vals  = np.asarray(cnf.offrates)
    roff  = np.empty(shape, dtype = 'f4')
    if np.any(vals <= 0.):
        roff[:,vals <= 0.] = cnf.duration//(len(cnf.positions)+1)
    if np.any(vals > 0.):
        good         = vals > 0.
        roff[:,good] = rnd.poisson(vals[good], size = (shape[0], np.sum(good)))

    roff[~ron] = 0.
    roff[np.cumsum(roff, axis = 1) > cnf.duration] = 0.
    return roff

def eventstobead(cnf: Experiment, events: np.ndarray = None) -> np.ndarray:
    """
    create bead data from events.

    This does not include any type of noise
    """
    inds    = cnf.phaseindexes()
    base    = np.zeros((cnf.ncycles, inds[-1]), dtype = 'f4')

    for i in (cnf.protocol.initial, cnf.protocol.pull, cnf.protocol.relax):
        base[:,inds[i]:inds[i+1]] = cnf.phasez(i)

    def _lin(first, sec, phase):
        size = cnf.phases[phase]
        return ((sec-first)*(np.arange(size)/(size+1)+1./(size+1.))[:,None] + first).T

    base[:,inds[0]:inds[1]] = _lin(cnf.phasez(7),     base[:, inds[1]], 0)
    base[:,inds[2]:inds[3]] = _lin(base[:,inds[2]-1], base[:, inds[3]], 2)
    base[:,inds[4]:inds[5]] = _lin(base[:,inds[4]-1], cnf.phasez(cnf.protocol.rampdown), 4)
    base[:,inds[6]:inds[7]] = _lin(base[:,inds[6]-1], base[:, inds[7]], 6)

    if events is not None and len(cnf.positions):
        pos = cnf.positions
        for vect, evts in zip(base[:, inds[5]:inds[6]], np.cumsum(np.int32(events), axis = 1)):
            vect[:evts[0]] = pos[0]
            for i, j in enumerate(pos[1:]):
                vect[evts[i]:evts[i+1]] = j

    return base

def createbead(cnf: Experiment, evts = None, drift = None, base = None, seed: RAND_STATE = None):
    """
    create one bead data
    """
    rnd  = randstate(seed)
    if evts is None:
        evts = poissonevents(cnf, rnd)
    bead = eventstobead(cnf, evts)

    if cnf.strandclosing:
        closing = cnf.strandclosing(cnf, bead, rnd)
    else:
        closing = None

    if cnf.brownianmotion:
        cnf.brownianmotion(cnf, bead, rnd)

    base  = (base                               if base is not None           else
             cnf.baseline(cnf, rnd)             if callable(cnf.baseline)     else
             np.zeros(bead.size, dtype = 'f4'))

    if drift is None and callable(cnf.thermaldrift):
        base  = np.copy(base)
        drift = cnf.thermaldrift(cnf, base, rnd)

    if base is not None:
        bead.ravel()[:] += base

    return BeadTruth(closing, evts, base, drift), bead.ravel()

def totrack(cnf: Experiment, nbeads: int = 1, seed: RAND_STATE = None, **kwa) -> Dict[str, Any]:
    """
    creates a track
    """
    rnd    = randstate(seed)

    base   = (cnf.baseline    (cnf, rnd)       if callable(cnf.baseline) else
              np.zeros(cnf.ncycles*cnf.phaseindexes('count')[0], dtype = 'f4'))
    drift  = cnf.thermaldrift(cnf, base, rnd) if callable(cnf.baseline) else None

    itms   = [createbead(cnf, None, drift, base, rnd) for i in range(nbeads)]
    ends   = np.repeat([list(cnf.phases)], cnf.ncycles, axis = 0).cumsum()
    phases = np.insert(ends, 0, 0)[:-1].reshape((cnf.ncycles, len(cnf.phases)))

    kwa.setdefault('framerate', 30.)
    kwa.setdefault('key',      'sim')
    kwa.update(data   = dict((i, j[1]) for i, j in enumerate(itms)),
               truth  = dict((i, j[0]) for i, j in enumerate(itms)),
               phases = phases)
    return kwa
