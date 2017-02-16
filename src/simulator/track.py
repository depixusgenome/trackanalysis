#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Simulates track files"
from    typing import Sequence, Union, Tuple, Optional # pylint: disable=unused-import
import  random
import  numpy as np

from    utils   import initdefaults, kwargsdefaults
from    data    import Track

class TrackSimulatorConfig:
    u"Config for simulating bead data over a number of cycles"
    ncycles      = 15
    phases       = [ 1,  15,  1, 15,  1, 100,  1,  15]
    zmax         = [ 0., 0., 1., 1., 0., 0., -.3, -.3]
    brownian     = [.003] * 8       # type: Union[None, float, Sequence[float]]
    randzargs    = (0., .1, .9)     # type: Optional[Tuple[float, float, float]]
    randtargs    = (10, 100)        # type: Optional[Tuple[int, int]]
    baselineargs = (.1, 10.1, True) # type: Optional[Tuple[float, float, bool]]
    driftargs    = (.1, 29.)        # type: Optional[Tuple[float, float]]
    @initdefaults
    def __init__(self, **_):
        pass

class TrackSimulator(TrackSimulatorConfig):
    u"Simulates bead data over a number of cycles"
    def addtemplate(self, cycles):
        u"basic shape of a cycle, without drift or events"
        rng  = [self.zmax[-1]]+list(self.zmax)
        ends = np.insert(np.cumsum(self.phases), 0, 0)
        for i in range(len(self.phases)):
            rho    = (rng[i+1]-rng[i])/(ends[i+1]-ends[i])
            dat    = cycles[:,ends[i]:ends[i+1]]
            dat[:] = rho * np.arange(ends[i+1]-ends[i])+rng[i]

    def randz(self, pos):
        u"Random z value for an event."
        floor, scale, maxz = self.randzargs
        if pos is None:
            pos = maxz
        return random.randint(int(floor/scale), int(pos/scale))*scale

    def randt(self, _):
        u"random event duration"
        return random.randint(*self.randtargs)

    def addevents(self, cycles):
        u"add events to the cycles"
        if None in (self.randtargs, self.randzargs):
            return

        for cyc in cycles[:,sum(self.phases[:5]) : sum(self.phases[:6])]:
            pos = None
            while len(cyc):
                pos        = self.randz(pos)
                ind        = self.randt(pos)
                cyc[:ind] += pos
                cyc        = cyc[len(cyc[:ind]):]

    def baseline(self, ncycles):
        u"The shape of the baseline"
        size = sum(self.phases)
        if self.baselineargs is None:
            return np.zeros((ncycles, size), dtype = 'f4')

        amp, scale, stairs = self.baselineargs
        if stairs:
            base = np.repeat(np.cos(np.arange(ncycles)*2.*np.pi/scale) * amp, size)
        else:
            base = np.cos(np.arange(ncycles*size)*2.*np.pi/(size*scale)) * amp

        base = base.reshape((ncycles, size))
        return base

    def addbaseline(self, cycles):
        u"add events to the cycles"
        if self.baselineargs is None:
            return

        cycles += self.baseline(len(cycles))

    @property
    def drift(self):
        u"drift shape"
        cycles = np.zeros((1, sum(self.phases)), dtype = 'f4')
        self.adddrift(cycles)
        return cycles.ravel()

    def adddrift(self, cycles):
        u"adds a drift to cycles"
        if self.driftargs is None:
            return

        amp, scale = self.driftargs
        size       = sum(self.phases[:4])

        driftup    = np.exp((np.arange(size)-size+1)/scale)
        driftup   -= driftup[0]
        driftup   *= amp/driftup[-1]

        driftdown  = np.exp(-np.arange(sum(self.phases)-size+1)/scale)
        driftdown -= driftdown[-1]
        driftdown *= driftup[-1]/driftdown[0]

        cycles[:,:size] += driftup
        cycles[:,size:] += driftdown[1:]

    _NONE = type('__none__', tuple(), {})
    def addbrownian(self, cycles, brownian = _NONE):
        u"add brownian noise to the cycles"
        if brownian is self._NONE:
            brownian = self.brownian

        if brownian is None:
            return

        elif isinstance(brownian, (float, int)):
            if brownian > 0.:
                cycles[:] += np.random.normal(0., brownian, cycles.shape)

        elif isinstance(brownian, Sequence[Union[float,int]]):
            ends = np.insert(np.cumsum(self.phases), 0, 0)
            for i in range(len(self.phases)):
                self.addbrownian(cycles[:,ends[i]:ends[i+1]], brownian[i])

        elif callable(brownian):
            cycles[:] += np.random.normal(0., brownian(cycles), cycles.shape)

    @property
    def cycles  (self):
        u"returns an array of cycles start positions"
        ends = np.repeat([list(self.phases)], self.ncycles, axis = 0).cumsum()
        return np.insert(ends, 0, 0)[:-1].reshape((self.ncycles, len(self.phases)))

    @staticmethod
    def seed(seed):
        u"sets the random seeds to a single value"
        if seed is not None:
            np.random.seed(seed)
            random.seed(seed)

    def __call__(self, seed = None):
        self.seed(seed)
        cycles = np.zeros((self.ncycles, sum(self.phases)), dtype = 'f4')
        self.addtemplate(cycles)
        self.addevents  (cycles)
        self.addbaseline(cycles)
        self.adddrift   (cycles)
        self.addbrownian(cycles)
        return cycles.ravel()

    @kwargsdefaults
    def track(self, nbeads = 1., seed = None):
        u"creates a simulated track"
        self.seed(seed)
        return Track(data   = {i: self() for i in range(nbeads)},
                     cycles = self.cycles)
