#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Creates peaks at various positions"
from   typing   import (Union, Sequence, Optional, # pylint: disable=unused-import
                        Dict, Tuple)
import random
import numpy as np
from   numpy.lib.stride_tricks  import as_strided

from   utils                    import initdefaults, kwargsdefaults

class FakeTrack:
    u"Placeholder"
    def __init__(self):
        self.data  = dict()
        self.beads = self.data

class PeakSimulator:
    u"""
    Configuration for simulating cycle peaks. Calling this functor will return
    a list containing a list of peak positions. If labels are provided, these are
    returned in an adjoining list of similar shape.

    Fields:

    * *peaks*:  list of peak positions that can occur
    * *labels*: list of peak labels. Can be None in which case labels are not returned.
        Can be "peaks" in which case the exact peak positions used as labels.
        Can be "range" in which case the peak indexes are used as labels.
    * *rates*: peak rates between 0 and 1. This can be a single value in which
        case all peaks have the same rate, or it can be one value per peak. Setting
        this field to *None* is the same as setting it to *1*.
    * *brownian*: a float value indicating the amount of random displacement to
        add to every peak individually. This randomness is due to the brownian
        motion of the bead.
    * *bias*: a float value indicating the amount of random displacement to add
        to all peaks in a list. This randomness comes from the changing baseline
        from cycle to cycle or experiment to experiment.
    * *stretch*: a float value indicating the  random factor by wich to
        multiplie all peak positions in a list. This randomness comes from the
        changing baseline from cycle to cycle or experiment to experiment.
    * *sizes*: used only with PeakSimulator.events, defines the size of events.
      If an int is provided, all events have that size. If a pair of ints is
      provided, events have a random size in the provided range.
    """
    peaks    = np.arange(10)*10.
    labels   = None     # type: Union[None, Sequence, str]
    rates    = .1       # type: Union[None, float, Sequence[float]]
    brownian = .1       # type: Optional[float]
    bias     = .1       # type: Optional[float]
    stretch  = .1       # type: Optional[float]
    sizes    = (5, 20)  # type: Optional[Tuple[int,int]]
    __KEYS   = frozenset(locals())
    @initdefaults(__KEYS)
    def __init__(self, **_):
        pass

    def __return(self, occs, peaks):
        if   isinstance(self.labels, str):
            flag = self.labels.lower()
            if flag == 'peaks':
                pos = np.asarray(self.peaks) # notice that dtype is not specified
            elif flag == 'range':
                pos = np.arange(len(self.peaks))
            else:
                raise KeyError()

        elif isinstance(self.labels, Sequence):
            pos = np.asarray(self.labels)

        else:
            return peaks

        labels    = np.empty_like(peaks)
        labels[:] = [pos[i] for i in occs]
        return peaks, labels

    @staticmethod
    def seed(seed):
        u"sets the random seeds to a single value"
        if seed is not None:
            np.random.seed(seed)
            random.seed(seed)

    def selectpeaks(self, ncycles):
        u"Selects peaks for each cycle"
        npeaks = len(self.peaks)
        if self.rates is None:
            occs = np.ones((ncycles, npeaks), dtype = 'bool')
        else:
            vals = np.random.rand(ncycles*npeaks).reshape((ncycles, npeaks))

            if np.isscalar(self.rates):
                occs = vals < self.rates
            else:
                occs = vals < np.asarray(self.rates)

        peaks    = np.empty((ncycles,), dtype = 'O')
        pos      = np.asarray(self.peaks, dtype = 'f4')
        peaks[:] = [pos[i] for i in occs]
        return occs, peaks

    def addstretch(self, peaks):
        u"changes the stretch for each cycle"
        if self.stretch is None:
            return

        peaks[:] *= 1. + (np.random.rand(len(peaks))*2.-1.)*self.stretch

    def addbias(self, peaks):
        u"moves each cycle a bit"
        if self.bias is None:
            return

        peaks[:] += (np.random.rand(len(peaks))*2.-1.)*self.bias

    def addbrownian(self, peaks):
        u"returns a flat random value"
        if self.brownian is None:
            return

        rngs = np.concatenate(([0], np.cumsum([len(i) for i in peaks])))
        rngs = as_strided(rngs,
                          shape   = (len(rngs)-1, 2),
                          strides = (rngs.strides[0],)*2)

        vals = np.float32(np.random.normal(0., self.brownian, rngs[-1,-1]))
        for i, sli in enumerate(rngs):
            peaks[i] += vals[sli[0]:sli[1]]

    def peakstoevents(self, peaks):
        u"""
        Changes peaks to events.

        Returns an array of concatenated events and an array of events
        """
        nevts  = np.array([len(i) for i in peaks])

        if isinstance(self.sizes, int):
            sizes = np.full((nevts.sum(),), self.sizes, dtype = 'i4')
        elif isinstance(self.sizes, tuple):
            sizes = np.random.randint(self.sizes[0], self.sizes[1], nevts.sum(), 'i4')
        else:
            raise TypeError("PeakSimulator.sizes: "+str(type(self.sizes)))

        if len(sizes) == 0:
            sizes = np.ones((len(peaks),), dtype = 'i4')
        else:
            sizes = np.insert(sizes, np.where(nevts == 0)[0], 1)

        if self.brownian is not None:
            bead = np.float32(np.random.normal(0., self.brownian, sizes.sum()))
        else:
            bead = np.zeros((sizes.sum(),), dtype = 'f4')
        events = np.empty((len(peaks),), dtype = 'O')

        tsize  = sizes[:]
        tbead  = bead[:]
        for cid, cycle in enumerate(peaks):
            npeaks  = max(1, len(cycle))
            nframes = tsize[:npeaks].sum()

            if len(cycle):
                tbead[:nframes] += np.repeat(cycle, tsize[:npeaks])

            rngs         = np.insert(np.cumsum(tsize[:npeaks]), 0, 0)
            rngs         = as_strided(rngs,
                                      shape   = (len(cycle), 2),
                                      strides = (rngs.strides[0],)*2)

            events[cid]        = np.empty((len(cycle),), dtype = 'O')
            if len(cycle):
                events[cid][:] = [tbead[i:j] for i, j in rngs]

            tbead = tbead[nframes:]
            tsize = tsize[npeaks:]

        return bead, events

    @kwargsdefaults(__KEYS)
    def __call__(self, ncycles, seed = None):
        self.seed(seed)

        occs, peaks = self.selectpeaks(ncycles)

        self.addbrownian(peaks)
        self.addstretch (peaks)
        self.addbias    (peaks)

        return self.__return(occs, peaks)
