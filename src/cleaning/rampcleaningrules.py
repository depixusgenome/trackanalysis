#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Removing aberrant points and cycles from Ramps"
from abc import ABC, abstractmethod
from typing import Dict
import numpy as np

from ._core import ExtentRule  # pylint: disable=import-error
from ._core import Partial  # pylint: disable=import-error


class CleaningRuleBase(ABC):
    """Base class for cleaning-rules.

    All configurations are to be stored as attributes.
    The configuration can be set with `configure()` and retrieved with `config()`.

    A cleaning rule is applied by calling an instance of an implementing class.
    Any inheriting class must therefore implement the `__call__` method which should
    return a `Partial` object.
    """
    def __init__(self, **kwa):
        self.configure(**kwa)

    @abstractmethod
    def __call__(self, bead, start, stop):
        pass

    def configure(self, **kwa):
        "Update each attribute of the class with the value passed as named argument"
        for conf, val in kwa.items():
            if conf in self.__dict__:
                setattr(self, conf, val)
            # else:
            #     raise KeyError(
            #         str(self.__class__) + " has no attribute '" + str(conf) + "' to configure")

    def config(self) -> Dict[str, float]:
        "Return the default configuration of the Rule."
        return {attr: val for attr, val in self.__dict__.items() if not attr.startswith('_')}


class ExtentOutliersRule(CleaningRuleBase):
    """Remove cycles with extent-outliers"""
    name = "extentoutliers"
    def __init__(self, **kwa):
        super().__init__(**kwa)
        self.extentoutlierspercentile: float = 90
        self.minextentoutliers: float = 90
        self.maxextentoutliers: float = 110

    def __call__(self, bead, start, stop) -> Partial:
        "Detect the cycles which do *not* open with the consenus-extent."
        extents = ExtentRule().extent(bead, start, stop).values  # the extents for each cycle

        if len(extents) <= 2:
            return Partial(self.name,
                           np.empty(0, dtype='i4'),
                           np.empty(0, dtype='i4'),
                           1.0)

        consensus = np.percentile(extents, self.extentoutlierspercentile)

        normalized_extents = extents / consensus

        minv = np.sort(np.argwhere(extents < self.minextentoutliers/100 * consensus).flatten())
        maxv = np.sort(np.argwhere(extents > self.maxextentoutliers/100 * consensus).flatten())

        return Partial(name=self.name,
                       min=minv,
                       max=maxv,
                       values=normalized_extents)
