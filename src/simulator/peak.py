#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Creates peaks at various positions"
from   typing   import  Union, Sequence, Optional # pylint: disable=unused-import
import random
import numpy as np

from utils import initdefaults

class PeakSimulatorConfig:
    u"Configuration for simulating cycle peaks"
    peaks    = np.arange(10)*10.
    rates    = .1   # type: Union[None, float, Sequence[float]]
    brownian = .1   # type: Optional[float]
    bias     = .1   # type: Optional[float]
    stretch  = .1   # type: Optional[float]
    @initdefaults('peaks', 'rates', 'brownian', 'bias', 'stretch')
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

    def occurence(self):
        u"returns a flat random value"
        if self.rates is None:
            return slice(None, None)
        return np.random.rand(len(self.peaks)) < self.rates

    @staticmethod
    def rand(factor):
        u"returns a flat random value"
        return 0. if factor is None else (np.random.rand()*2.-1.)*factor

    def normal(self, shape = None):
        u"returns a flat random value"
        if self.brownian is None:
            return 0.
        return np.random.normal(0., self.brownian, shape)

    def __call__(self, ncycles, seed = None):
        self.seed(seed)
        res = np.empty((ncycles,), dtype = 'O')
        for i in range(ncycles):
            peaks  = self.peaks[self.occurence()]
            peaks += self.normal(peaks.shape)

            peaks *= 1.+self.rand(self.stretch)
            peaks += self.rand(self.bias)

            res[i] = peaks
        return res
