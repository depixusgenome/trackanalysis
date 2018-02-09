#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Simulates binding events"
from copy   import copy
from enum   import Enum
from typing import Dict, Any, FrozenSet, Callable, Optional, cast

import numpy  as np

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
    rateon  : float = 1.
    rateoff : float = 0.
    _ARGS  = Object.args(set(locals()) | {'position'})
    def __init__(self, position, **kwa):
        super().__init__(position = position, **kwa)

class ThermalDrift:
    """
    Add thermal drift to each cycle
    """
    tscale = 30.
    zscale = 1e-2
    def __call__(self, cnf, bead):
        if None in (self.tscale, self.zscale):
            return
        inds       = cnf.phaseindexes
        size       = inds[4]-inds[2]

        driftup    = np.exp((np.arange(size)-size+1)/self.tscale)
        driftup   -= driftup[0]
        driftup   *= self.zscale/driftup[-1]
        bead[:,inds[2]:inds[4]] += driftup

        driftdown  = np.exp(-np.arange(inds[6]-inds[4])/self.tscale)
        driftdown -= driftdown[-1]
        driftdown *= driftup[-1]/driftdown[0]

        bead[:,inds[4]:inds[6]] += driftdown

class BaseLine:
    """
    Add baseline to bead
    """
    sigma = 5e-3
    knee  = 30./1e3
    alpha = 1.
    def __call__(self, cnf):
        size    = cnf.ncycles * np.sum(cnf.phases)
        #generate white noise in time domain
        #shaping in freq domain
        fft     = getattr(np, 'fft')
        signal  = fft.rfft(np.random.normal(0., self.sigma, size))
        tmp     = fft.fftfreq(size, d=1.)[:len(signal)]
        tmp[-1] = np.abs(tmp[-1])

        # set mean to 0.
        signal[0]     = 0.

        good          = np.logical_and(tmp < self.knee, tmp != 0.)
        signal[good] *= np.abs((tmp[good]/self.knee)**(-self.alpha))

        # discard high-freq amplitudes
        signal[tmp>self.knee]  = 0.
        return fft.irfft(signal)

class Experiment(Object):
    """
    Information on the experiment

    # Attributes

    * *ncycles*: number of cycles

    * *durartion*: max duration of phase 5
    """
    ncycles                = 100
    sigma: Optional[float] = 2.e-3
    bindings               = [Binding(i) for i in (1., .8, .5, .2, .1)]
    phases                 = [5, 20, 5, 20, 10, 100, 5, 20]
    baseline               = None
    thermaldrift           = None
    _ARGS                  = Object.args(locals())
    def __init__(self, **kwa):
        super().__init__(**kwa)
        if 'positions' in kwa:
            if 'bindings' in kwa:
                raise KeyError("don't use both bindings and positions keywords")
            self.bindings = kwa['positions']
        self.bindings = [(Binding(i) if np.isscalar(i)         else
                          i          if isinstance(i, Binding) else
                          Binding(**i))
                         for i in self.bindings]
        for i in {'rateon', 'rateoff'} & set(kwa):
            val = (np.full(len(self.bindings), kwa[i], dtype = 'f4')
                   if np.isscalar(kwa[i]) else kwa[i])
            for bind, itm in zip(self.bindings, val):
                setattr(bind, i, itm)

        if self.thermaldrift is True:
            self.thermaldrift = ThermalDrift()

        if self.baseline is True:
            self.baseline = BaseLine()

    setup  = __init__

    @property
    def phaseindexes(self) -> np.ndarray:
        "return the phase indexes from phase 0"
        return np.cumsum(np.insert(self.phases, 0, 0))

    def phasez(self, val)-> float:
        "phase 3 extension"
        if val == 1:
            return 0.
        if val == 3:
            return max(self.positions)*1.1
        return -.1

    def phasesigma(self, val)-> float:
        "phase 3 extension"
        if val == 1:
            return self.sigma
        if val == 3:
            return self.sigma*.5
        return self.sigma*3.

    @property
    def duration(self)-> int:
        "phase 5 duration"
        return self.phases[5]

    @property
    def positions(self) -> np.ndarray:
        """
        Return position of bindings
        """
        return np.array([i.position for i in self.bindings], dtype = 'f4')
    @property
    def rateon(self) -> np.ndarray:
        """
        Return rate of bindings
        """
        return np.array([i.rateon for i in self.bindings], dtype = 'f4')

    @property
    def rateoff(self) -> np.ndarray:
        """
        Return rate of bindings
        """
        return np.array([i.rateoff for i in self.bindings], dtype = 'f4')

    @property
    def nature(self) -> np.ndarray:
        """
        Return nature of bindings
        """
        return np.array([i.nature for i in self.bindings], dtype = 'f4')

def poissonevents(cnf: Experiment, seed: int = None) -> np.ndarray:
    """
    Creates events using provided positions, rates and durations.
    """
    rnd   = np.random.RandomState(seed)
    shape = (cnf.ncycles, len(cnf.positions))
    ron   = rnd.rand(*shape) < cnf.rateon

    vals  = cnf.rateoff
    roff  = np.empty(shape, dtype = 'f4')
    if np.any(vals <= 0.):
        roff[:,vals <= 0.] = cnf.duration//(len(cnf.positions)+1)
    if np.any(vals > 0.):
        good         = vals > 0.
        roff[:,good] = rnd.poisson(vals[good], size = (shape[0], np.sum(good)))

    roff[~ron] = 0.
    roff[np.cumsum(roff, axis = 1) > cnf.duration] = 0.
    return roff

def brownianmotion(cnf: Experiment, events: np.ndarray, seed : int = None) -> np.ndarray:
    """
    Add brownian motion
    """
    if not cnf.sigma:
        return
    noise = np.random.RandomState(seed).normal
    if len(events.shape) == 1 or events.shape[1] == len(cnf.bindings):
        events += np.cumsum(noise(0., cnf.sigma, events.shape), axis = 1)
    else:
        brown   = np.zeros(events.shape, dtype = 'f4')
        inds    = cnf.phaseindexes
        size    = cnf.ncycles

        brown[:,:inds[1]]        += noise(0., cnf.phasesigma(7), (size, inds[1]))
        brown[:,inds[1]:inds[3]] += noise(0., cnf.phasesigma(1), (size, inds[3]-inds[1]))
        brown[:,inds[3]:inds[5]] += noise(0., cnf.phasesigma(3), (size, inds[5]-inds[3]))
        brown[:,inds[5]:inds[7]] += noise(0., cnf.phasesigma(5), (size, inds[7]-inds[5]))
        brown[:,inds[7]:]        += noise(0., cnf.phasesigma(7), (size, inds[8]-inds[7]))
        events += np.cumsum(brown, axis = 1)

def tobead(cnf: Experiment, events: np.ndarray = None, seed:int = None) -> np.ndarray:
    """
    create bead data from events.

    This does not include any type of noise
    """
    rnd     = np.random.RandomState(seed)
    inds    = cnf.phaseindexes
    base    = np.zeros((cnf.ncycles, inds[-1]), dtype = 'f4')

    fcn     = (cnf.phasez if not cnf.sigma else
               lambda x: rnd.normal(cnf.phasez(x), cnf.phasesigma(x), cnf.ncycles)[:,None])
    base[:,inds[1]:inds[2]] = fcn(1)
    base[:,inds[3]:inds[4]] = fcn(3)
    base[:,inds[7]:inds[8]] = fcn(7)

    def _lspace(first, sec, phase):
        size = cnf.phases[phase]
        return ((sec-first)*(np.arange(size)/(size+1)+1./(size+1.))[:,None] + first).T
    base[:,inds[0]:inds[1]] = _lspace(cnf.phasez(7),     base[:, inds[1]],   0)
    base[:,inds[2]:inds[3]] = _lspace(base[:,inds[2]-1], base[:, inds[3]],   2)
    base[:,inds[4]:inds[5]] = _lspace(base[:,inds[4]-1], max(cnf.positions), 4)
    base[:,inds[6]:inds[7]] = _lspace(base[:,inds[6]-1], base[:, inds[7]],   6)

    if events is not None and len(cnf.positions):
        pos = cnf.positions
        for vect, evts in zip(base[:, inds[5]:inds[6]], np.cumsum(np.int32(events), axis = 1)):
            vect[:evts[0]] = pos[0]
            for i, j in enumerate(pos[1:]):
                vect[evts[i]:evts[i+1]] = j
    return base

def totrack(cnf: Experiment, nbeads:int = 1, seed:int = None, **kwa) -> Dict[str, Any]:
    """
    creates a track
    """
    ends   = np.repeat([list(cnf.phases)], cnf.ncycles, axis = 0).cumsum()
    phases = np.insert(ends, 0, 0)[:-1].reshape((cnf.ncycles, len(cnf.phases)))

    base   = cast(Callable, cnf.baseline)(cnf) if callable(cnf.baseline) else None
    def _run():
        evts = poissonevents(cnf, seed)
        bead = tobead(cnf, evts)
        if cnf.thermaldrift:
            cnf.thermaldrift(cnf, bead)
        if base is not None:
            bead.ravel()[:] += base
        brownianmotion(cnf, bead, seed)
        return evts, bead.ravel()

    itms = [_run() for i in range(nbeads)]
    kwa.setdefault('framerate', 30.)
    kwa.setdefault('key',      'sim')
    kwa.update(data   = dict((i, j[1]) for i, j in enumerate(itms)),
               events = dict((i, j[0]) for i, j in enumerate(itms)),
               phases = phases)
    return kwa
