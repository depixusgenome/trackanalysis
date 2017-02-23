#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Simulates track files"
from    typing          import (Sequence, Union, # pylint: disable=unused-import
                                Optional, NamedTuple, Iterable,
                                Callable, Iterator, Any, Tuple)
import  random
from    itertools       import chain

import  numpy as np

from    utils           import initdefaults, kwargsdefaults
from    data            import Track
from    data.trackitems import Cycles, Level

class LadderEvents:
    u""" Creates events on a given range """
    randzargs    = (0., .1, .9)     # type: Optional[Tuple[float, float, float]]
    randtargs    = (10, 100)        # type: Optional[Tuple[int, int]]
    @initdefaults
    def __init__(self, **_):
        pass

    def randz(self, pos):
        u"Random z value for an event."
        floor, scale, maxz = self.randzargs
        if pos is None:
            pos = maxz
        return random.randint(int(floor/scale), int(pos/scale))*scale

    def randt(self, _):
        u"random event duration"
        return random.randint(*self.randtargs)

    def __call__(self, cycles: np.ndarray) -> np.ndarray:
        u"add events to the cycles"
        if None in (self.randtargs, self.randzargs):
            return

        for cyc in cycles:
            pos = None
            while len(cyc):
                pos        = self.randz(pos)
                ind        = self.randt(pos)
                cyc[:ind] += pos
                cyc        = cyc[len(cyc[:ind]):]

class PoissonEvents:
    u"""
    Creates events using provided positions, rates and durations.

    Fields are:

    * *peaks*: event positions.

    * *rates*: event rate of apparition. Can be a float in which case all peaks
    have the same rate. A *None* value is the same as a rate of 1 for all peaks.

    * *durations*: the average event size (poissonian distribution).
    It can be a float in which case all peaks have the same probable duration.
    A *None* indicates that all occurring events have the same duration fraction
    of a cycle. *duration* is in number of frames.

    **Note:** the peak at zero is implicit. It occurs unless stochastic events
    last too long.
    """
    peaks     = [.1, .3, .5, .9, 1.5]   # type: Sequence[float]
    rates     = 1.                      # type: Union[None,float,Sequence[float]]
    durations = None                    # type: Union[None,float,Sequence[float]]
    @initdefaults
    def __init__(self, **_):
        pass

    def __durations(self, occ, cycsize):
        peaks = np.asarray(self.peaks, dtype = 'f4')
        sorts = np.argsort(peaks)[::-1]
        peaks = peaks[sorts]
        if not self.durations:
            dur = np.repeat(cycsize//(np.sum(occ, 1)+1), len(peaks))
            dur = dur.reshape(occ.shape)
        else:
            if isinstance(self.durations, (float, int)):
                dur = np.random.poisson(self.durations, occ.shape)
            else:
                values = np.asarray(self.durations)[sorts]
                dur = np.array([np.random.poisson(val, len(peaks))
                                for val in values], dtype = 'f4')
        dur[~occ] = 0
        np.cumsum(dur, 1, out = dur)
        return peaks, dur

    def __call__(self, cycles: np.ndarray) -> np.ndarray:
        u"add events to the cycles"
        rates       = self.rates if self.rates else 1.
        occs        = np.random.rand(len(cycles), len(self.peaks)) < rates  # type: ignore
        peaks, durs = self.__durations(occs, cycles.shape[1])
        inds        = 1+np.apply_along_axis(np.searchsorted, 1, durs, cycles.shape[1])
        for ind, cyc, dur, occ in zip(inds, cycles, durs, occs):
            occ = occ[:ind]
            for rng, peak in zip(np.split(cyc, dur[:ind][occ]), peaks[:ind][occ]):
                rng[:] = peak

class TrackSimulator:
    u"Simulates bead data over a number of cycles"
    DTYPE        = np.dtype([('start', 'i4'), ('data', 'O')])
    ncycles      = 15
    phases       = [ 1,  15,  1, 15,  1, 100,  1,  15]
    zmax         = [ 0., 0., 1., 1., 0., 0., -.3, -.3]
    events       = PoissonEvents()      # type: Callable[..., np.ndarray]
    brownian     = [.003] * 8           # type: Union[None, float, Sequence[float]]
    baselineargs = (.1, 10.1, True)     # type: Optional[Tuple[float, float, bool]]
    driftargs    = (.1, 29.)            # type: Optional[Tuple[float, float]]
    @initdefaults(events = 'update')
    def __init__(self, **_):
        pass

    def __call__(self, seed = None):
        self.seed(seed)
        return self.__apply(np.ravel)

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

    def drift(self, cycles = None):
        u"drift shape"
        if cycles is None:
            cycles = np.zeros((1, sum(self.phases)), dtype = 'f4')

        if self.driftargs is not None:
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
        return cycles.ravel()

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

    @kwargsdefaults
    def track(self, nbeads = 1, seed = None):
        u"creates a simulated track"
        self.seed(seed)
        return Track(data = {i: self() for i in range(nbeads)}, cycles = self.cycles)

    @kwargsdefaults
    def beads(self, nbeads = 1, seed = None):
        u"creates a simulated track"
        return self.track(nbeads, seed).beads

    @kwargsdefaults
    def bybeadevents(self, nbeads, seed = None) -> Cycles: # pylint: disable=arguments-differ
        u"Creates events in a Events object"
        self.seed(seed)

        evts  = dict()      # type: Dict[Tuple[int,int], np.ndarray]
        def _create(cycles, bead):
            evts.update(((bead, cid), evt) for cid, evt in enumerate(self.__events(cycles)))
            return cycles.ravel()

        data  = dict((bead, self.__apply(_create, bead)) for bead in range(nbeads))
        track = Track(data = data, cycles = self.cycles)
        return Cycles(track = track, data = evts, direct = True, level = Level.event)

    @kwargsdefaults
    def bypeakevents(self, nbeads, seed = None):
        u"Creates events grouped by peaks"
        self.seed(seed)

        def _create(cycles):
            events = tuple(self.__events(cycles))
            labels = [np.array([i[0] for i in evt['data']]) for evt in events]
            curs   = []
            for lab in np.unique(np.concatenate(labels)):
                cur          = np.empty((len(events),), dtype = self.DTYPE)
                cur['start'] = sum(self.phases[:5])
                cur['data']  = None
                for i, (cevt, clab) in enumerate(zip(events, labels)):
                    val = cevt[clab == lab]
                    if len(val):
                        cur[i] = (val[0]['start'], val[0]['data'])
                curs.append(cur)
            return curs

        def _generator():
            for cur in self.__apply(_create):
                peak = np.mean([i[1].mean() for i in cur if i[1] is not None])
                yield (peak, cur)

        for bead in range(nbeads):
            yield (bead, _generator())

    def __events(self, cycles: np.ndarray) -> Iterator[np.ndarray]:
        dtpe  = self.DTYPE
        start = np.sum(self.phases[:5])
        for cyc in self.__cyclephase(cycles, 5):
            rng  = np.nonzero(np.diff(cyc))[0]+1
            evts = [(i+start, evt) for i, evt in zip(chain((0,), rng), np.split(cyc, rng))]
            yield np.array(evts, dtype = dtpe)

    def __apply(self, fcn:Callable[...,Any], *args):
        u"Creates events in a Events object"
        cycles = np.zeros((self.ncycles, sum(self.phases)), dtype = 'f4')
        self.__addtemplate(cycles)
        if self.events is not None:
            self.events(self.__cyclephase(cycles, 5))

        ret = fcn(cycles, *args)

        if self.baselineargs is not None:
            cycles += self.baseline(len(cycles))

        self.drift(cycles)
        self.__addbrownian(cycles)
        return ret

    def __cyclephase(self, cycles:np.ndarray, phase:int) -> np.ndarray:
        first = sum(self.phases[:phase])
        return cycles[:,first:first+self.phases[phase]]

    def __addtemplate(self, cycles):
        u"basic shape of a cycle, without drift or events"
        rng  = [self.zmax[-1]]+list(self.zmax)
        ends = np.insert(np.cumsum(self.phases), 0, 0)
        for i in range(len(self.phases)):
            rho    = (rng[i+1]-rng[i])/(ends[i+1]-ends[i])
            dat    = cycles[:,ends[i]:ends[i+1]]
            dat[:] = rho * np.arange(ends[i+1]-ends[i])+rng[i]

    _NONE = type('__none__', tuple(), {})
    def __addbrownian(self, cycles, brownian = _NONE):
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
                self.__addbrownian(cycles[:,ends[i]:ends[i+1]], brownian[i])

        elif callable(brownian):
            cycles[:] += np.random.normal(0., brownian(cycles), cycles.shape)
