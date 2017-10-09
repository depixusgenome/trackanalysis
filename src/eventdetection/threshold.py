#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Defines thresholds on an array of characteristics"

from    abc          import ABC, abstractmethod

import  numpy as np

from    utils        import initdefaults

class Threshold(ABC):
    "Computes a threshold"
    @abstractmethod
    def __call__(self, data:np.ndarray, deltas:np.ndarray, precision:float) -> float:
        pass

class MedianThreshold(Threshold):
    """
    A threshold relying on the deltas.

    The threshold is set at at *distance* times the *precision* above *percentile*
    values of the grade provided.
    """
    percentile = 75.
    distance   = 2.
    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        super().__init__()

    def __call__(self, _1:np.ndarray, deltas:np.ndarray, precision:float) -> float:
        return np.percentile(deltas, self.percentile) + self.distance*precision

class PopulationThreshold(Threshold):
    """
    A threshold relying on the deltas.

    A standard-deviation type distance is estimated by considering the population
    interval *deviation*.

    The threshold is set at at *distance* times that estimation *precision*
    above *outliers* values of the grade provided.
    """
    outliers  = 75.
    deviation = [33., 66.]
    distance  = 2.
    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        super().__init__()

    def __call__(self, _1:np.ndarray, deltas:np.ndarray, _2:float) -> float:
        low, mid, high = np.percentile(deltas, self.deviation+[self.outliers])
        return high+(mid-low)*self.distance
