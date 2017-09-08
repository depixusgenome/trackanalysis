#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Matching experimental peaks to one another
"""
from    scipy.interpolate  import interp1d
import  numpy              as     np

from    ._base             import GriddedOptimization, Distance, DEFAULT_BEST


class ReferenceDistance(GriddedOptimization):
    """
    Matching experimental peaks by correlating peak positions in the histograms
    """
    symmetry = True
    def ___call__(self, aleft, aright):
        left  = self.__get(aleft)
        right = self.__get(aright)
        fcn   = self.__sym if self.symmetry else self.__asym
        return min((Distance(fcn(left, right, i), *i) for i in self.grid),
                   Distance(DEFAULT_BEST, 1., 0.))

    @staticmethod
    def __get(left):
        return (np.arange(len(left.table), dtype = 'f4')*left.binsize+left.minwidth,
                left.table)

    @classmethod
    def __sym(cls, left, right, params):
        return (cls.__asym(left, right, params)
                + cls.__asym(left, right, (1./params[0], -params[0]*params[1])))

    @staticmethod
    def __asym(left, right, params):
        return -(interp1d((right[0]-params[1])*params[0], right[1],
                          fill_value    = 0.,
                          bounds_error  = False,
                          assume_sorted = True)(left[0])
                 *left[1]).mean()
