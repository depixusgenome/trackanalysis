#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Creates peaks at various positions"
from   typing   import  Union, Sequence, Optional # pylint: disable=unused-import
import random
import numpy as np
from   numpy.lib.stride_tricks import as_strided

from utils import initdefaults, kwargsdefaults

class PeakSimulatorConfig:
    u"""
    Configuration for simulating cycle peaks. Calling this functor will return
    a list containing a list of peak positions. If labels are provided, these are
    returned in an adjoining list of similar shape.

    Fields:

    * *peaks*:  list of peak positions that can occur
    * *labels*: list of peak labels. Can be None in which case labels are not returned
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
    """
    peaks    = np.arange(10)*10.
    labels   = None # type: Optional[Sequence]
    rates    = .1   # type: Union[None, float, Sequence[float]]
    brownian = .1   # type: Optional[float]
    bias     = .1   # type: Optional[float]
    stretch  = .1   # type: Optional[float]
    @initdefaults
    def __init__(self, **_):
        pass

class PeakSimulator(PeakSimulatorConfig):
    u"Simulates cycles peaks"
    @staticmethod
    def seed(seed):
        u"sets the random seeds to a single value"
        if seed is not None:
            np.random.seed(seed)
            random.seed(seed)

    def occurence(self, ncycles):
        u"returns a flat random value"
        if self.rates is None:
            return slice(None, None)
        npeaks = len(self.peaks)
        vals   = np.random.rand(ncycles*npeaks).reshape((ncycles, npeaks))
        return vals < self.rates

    @staticmethod
    def __shaped(sizes, val):
        if np.isscalar(val):
            return np.full((len(sizes),), val, dtype = 'f4')
        else:
            return np.array([val[i:j] for i, j in sizes], dtype = 'O')

    @classmethod
    def rand(cls, shape, factor):
        u"returns a flat random value"
        vals = 0. if factor is None else (np.random.rand(shape[-1,-1])*2.-1.)*factor
        return cls.__shaped(shape, vals)

    def normal(self, shape):
        u"returns a flat random value"
        vals = 0.
        if self.brownian is not None:
            vals = np.random.normal(0., self.brownian, shape[-1,-1])
        return self.__shaped(shape, vals)

    @kwargsdefaults
    def __call__(self, ncycles, seed = None):
        self.seed(seed)
        occs   = self.occurence(ncycles)
        peaks  = np.array([self.peaks[i] for i in occs], dtype = 'O')

        rngs   = np.concatenate(([0], np.cumsum([len(i) for i in peaks])))
        rngs   = as_strided(rngs, shape = (len(rngs)-1, 2), strides = (rngs.strides[0],)*2)
        peaks += self.normal(rngs)
        peaks *= 1.+self.rand(rngs, self.stretch)
        peaks += self.rand(rngs, self.bias)

        if isinstance(self.labels, Sequence):
            # pylint: disable=unsubscriptable-object
            return peaks, np.array([self.labels[i] for i in occs], dtype = 'O')
        else:
            return peaks
