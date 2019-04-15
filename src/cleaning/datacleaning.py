#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Removing aberrant points and cycles"
from    typing                  import cast
import  numpy                   as     np
from    taskmodel.base          import Rescaler
# pylint: disable=import-error,unused-import
from    ._core                  import (constant as _cleaningcst, # pylint: disable=import-error
                                        clip     as _cleaningclip,
                                        DerivateSuppressor,
                                        LocalNaNPopulation,
                                        NaNDerivateIslands as DerivateIslands,
                                        AberrantValuesRule, PingPongRule,
                                        PopulationRule, HFSigmaRule, ExtentRule,
                                        SaturationRule, Partial)

class DataCleaning(
        Rescaler, # pylint: disable=too-many-ancestors
        AberrantValuesRule,
        HFSigmaRule,
        PopulationRule,
        ExtentRule,
        PingPongRule,
        SaturationRule,
        zattributes = (
            'maxabsvalue', 'maxderivate',   # AberrantValuesRule
            'minhfsigma',  'maxhfsigma',    # HFSigmaRule
            'minextent',   'maxextent',     # ExtentRurle
            'mindifference',                # PingPongRule
            'maxdisttozero'                 # SaturationRule
        )
):
    """
    Remove specific points, cycles or even the whole bead depending on a number
    of criteria implemented in aptly named methods:

    # `aberrant`
    {}

    # `hfsigma`
    {}

    # `population`
    {}

    # `extent`
    {}

    # `pingpong`
    {}

    # `saturation`
    {}

    # `pseudo code cleaning`
    Beads(trk) = set of all beads of the track trk <br>
    Cycles(bd) = set of all cycles in bead bd <br>
    Points(cy) = set of all points in cycle cy <br>
    <br>
    For a track trk, cleaning proceeds as follows:
    * for bd in Beads(trk):
        * remove aberrant values
        * for cy in Cycles(bd):
            * evaluate criteria for cy:
                1. population (not aberrant Points(cy)/Points(cy)) > 80%
                2. 0.25 < extent < 2.
                3. hfsigma < 0.0001
                4. hfsigma > 0.01
                5. the series doesn't bounce between 2 values
            * if 1. or 2. or 3. or 4. or 5. are FALSE:
                * remove cy from Cycles(bd)
            * else:
                * keep cy in Cycles(bd)
        * endfor
        * evaluate criteria for bd:
            5. population (Cycles(bd)/initial Cycles(bd)) > 80%
            6. saturation (Cycles(bd)) < 90%
        * if 5. or 6. are FALSE:
            * bd is bad
        * else:
            * bd is good
        * endif
    * endfor
    """
    CYCLES  = 'population', 'hfsigma', 'extent', 'pingpong'
    def __init__(self, **_):
        for base in DataCleaning.__bases__:
            base.__init__(self, **_) # type: ignore

    maxabsvalue = cast(float,
                       property(lambda self: self.derivative.maxabsvalue,
                                lambda self, val: setattr(self.derivative, 'maxabsvalue', val)))
    maxderivate = cast(float,
                       property(lambda self: self.derivative.maxderivate,
                                lambda self, val: setattr(self.derivative, 'maxderivate', val)))
    def __eq__(self, other):
        return all(base.__eq__(self, other) for base in DataCleaning.__bases__)

    def __getstate__(self):
        state = dict(self.__dict__)
        for base in DataCleaning.__bases__[1:]:
            state.update(base.__getstate__(self))
        return state

    def __setstate__(self, vals):
        self.__init__()
        self.__dict__.update({i: j for i, j in vals.items() if i in self.__dict__})
        for base in DataCleaning.__bases__[1:]:
            base.configure(self, vals)

    @staticmethod
    def badcycles(stats) -> np.ndarray:
        "returns all bad cycles"
        bad = np.empty(0, dtype = 'i4')
        if stats is None:
            return bad
        for stat in stats.values() if isinstance(stats, dict) else stats:
            bad = np.union1d(bad, stat.min)
            bad = np.union1d(bad, stat.max)
        return bad

    def aberrant(self, bead:np.ndarray, clip = False) -> bool:
        "remove abberant values"
        super().aberrant(bead, clip)
        return np.isfinite(bead).sum() <= len(bead) * self.minpopulation * 1e-2

# pybind11 bug
AberrantValuesRule.__base__.__setstate__ = lambda self, vals: self.configure(vals)

if DataCleaning.__doc__:
    DataCleaning.__doc__ = DataCleaning.__doc__.format(*(i.__doc__ for i in DataCleaning.__bases__))
