#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Tests cordrift"
import random
import numpy as np
from   data import Track

class BeadSimulator:
    u"""
    Simulates bead data over a number of cycles
    """
    def __init__(self, **kwa):
        self.ncycles   = kwa.get('ncycles',  15)
        self.phases    = kwa.get('phases',   [  1, 15,  1, 15,  1, 100,  1,  15])
        self.zmax      = kwa.get('zmax',     [-.3, 0., 0., 1., 1., 0., 0., -.3])
        self.randzargs = kwa.get('randz',   (0., .1, .9))
        self.randtargs = kwa.get('randt',   (10, 100))
        self.driftargs = kwa.get('drift',   (.1, 29.))

    def randz(self, pos):
        u"Random z value for an event."
        floor, scale, maxz = self.randzargs
        if pos is None:
            pos = maxz
        return random.randint(int(floor/scale), int(pos/scale))*scale

    def randt(self, _):
        u"random event duration"
        return random.randint(*self.randtargs)

    @property
    def drift(self):
        u"drift shape"
        cycles = np.zeros((1, sum(self.phases)), dtype = 'f4')
        self.adddrift(cycles)
        return cycles.ravel()

    def adddrift(self, cycles):
        u"adds a drift to cycles"
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

    def addbasic(self, cycles):
        u"basic shape of a cycle, without drift or events"
        rng  = [self.zmax[-1]]+list(self.zmax)
        ends = np.insert(np.cumsum(self.phases), 0, 0)
        for i in range(len(self.phases)):
            rho = (rng[i+1]-rng[i])/(ends[i+1]-ends[i])
            cycles[:,ends[i]:ends[i+1]] = rho * np.arange(ends[i+1]-ends[i])+rng[i]

    def addevents(self, cycles):
        u"add events to the cycles"
        for cyc in cycles[:,sum(self.phases[:5]) : sum(self.phases[:6])]:
            pos = None
            while len(cyc):
                pos        = self.randz(pos)
                ind        = self.randt(pos)
                cyc[:ind] += pos
                cyc        = cyc[len(cyc[:ind]):]

    @property
    def cycles  (self):
        u"returns an array of cycles start positions"
        ends = np.repeat([list(self.phases)], self.ncycles, axis = 0).cumsum()
        return np.insert(ends, 0, 0)[:-1].reshape((self.ncycles, len(self.phases)))

    def __call__(self, seed = None):
        if seed is not None:
            random.seed(seed)

        cycles = np.zeros((self.ncycles, sum(self.phases)), dtype = 'f4')
        self.addbasic(cycles)
        self.adddrift(cycles)
        self.addevents(cycles)
        return cycles.ravel()

    def track(self, nbeads = 1., seed = None):
        u"creates a simulated track"
        if seed is not None:
            random.seed(seed)
        return Track(data   = {i: self() for i in range(nbeads)},
                     cycles = self.cycles)
