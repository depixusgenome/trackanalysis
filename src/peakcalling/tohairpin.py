#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"""
Matching experimental peaks to hairpins
"""
from   typing       import (Dict, Sequence, NamedTuple, # pylint: disable=unused-import
                            Callable, Iterator, Iterable, Tuple, Any, Union, cast)
from   itertools    import product
import numpy        as np

from utils              import StreamUnion, kwargsdefaults, initdefaults
from sequences          import read as _read, peaks as _peaks
from ._core             import cost as _cost, match as _match # pylint: disable=no-name-in-module

OptimisationParams = NamedTuple('OptimisationParams',
                                [('threshold_param_rel', float),
                                 ('threshold_param_abs', float),
                                 ('threshold_func_rel',  float),
                                 ('stopval',             float),
                                 ('maxeval',             int)])

Range              = NamedTuple('Range',
                                [('min',  float),
                                 ('max',  float),
                                 ('step', float)])

class Hairpin:
    u"Matching experimental peaks to hairpins"
    peaks    = np.empty((0,), dtype = 'f4') # type: np.array
    lastpeak = False
    @initdefaults
    def __init__(self, **kwa):
        pass

    @staticmethod
    def topeaks(seq:str, oligos:Sequence[str]) -> np.ndarray:
        u"creates a peak sequence from a dna sequence and a list of oligos"
        return np.pad(np.array(_peaks(seq, oligos)['position'], dtype = 'i4'),
                      1, 'constant', constant_values = (0, len(seq)))

    @classmethod
    def read(cls, path : StreamUnion, oligos : Sequence[str]) -> 'Iterator[Hairpin]':
        u"creates a list of *Hairpin* from a fasta file and a list of oligos"
        return (cls(peaks = cls.topeaks(seq, oligos))
                for name, seq in _read(path))

Distance = NamedTuple('Distance', [('value', float), ('stretch', float), ('bias', float)])

class HairpinDistance(Hairpin):
    u"Matching experimental peaks to hairpins"
    DEFAULT_BEST = 1e20
    symmetry     = False
    precision    = 15.
    stretch      = Range(1./8.8e-4-200, 1./8.8e-4+200.01, 100.)
    bias         = Range(-20., 20.01, 20.)
    optim        = OptimisationParams(1e-4, 1e-8, 1e-4, 1e-8, 100)
    @initdefaults
    def __init__(self, **kwa):
        super().__init__(**kwa)

    @kwargsdefaults('precision', 'stretch', 'bias', 'lastpeak')
    def __call__(self, peaks : np.ndarray) -> Distance:
        best  = self.DEFAULT_BEST, sum(self.stretch[:2])*.5, sum(self.bias[:2])*.5
        delta = 0.
        if len(peaks) > 1:
            rng  = lambda x, y, z: (('min_'+x, y-z), (x, y), ('max_'+x, y+z))
            args = dict(symmetry            = self.symmetry, # type: ignore
                        noise               = self.precision,
                        threshold_param_rel = self.optim[0],
                        threshold_param_abs = self.optim[1],
                        threshold_func_rel  = self.optim[2],
                        stopval             = self.optim[3],
                        maxeval             = self.optim[4])

            hpin  = self.peaks if self.lastpeak else self.peaks[:-1]
            delta = peaks[0]
            peaks = peaks - peaks[0]

            optimize = _cost.optimize
            for vals in product(np.arange(*self.stretch), np.arange(*self.bias)):
                args.update(rng('stretch', vals[0], self.stretch.step))
                args.update(rng('bias',    vals[1], self.bias.step))
                try:
                    out = optimize(hpin, peaks, **args)
                except: # pylint: disable=bare-except
                    continue
                else:
                    if out[0] < best[0]:
                        best = out
        return Distance(best[0], best[1], best[2]-best[1]*delta)

PEAKS_DTYPE = np.dtype([('zvalue', 'f4'), ('key', 'f4')])
PEAKS_TYPE  = Union[Sequence[Tuple[float,float]],np.ndarray]
class PeakIdentifier(Hairpin):
    u"Identifying experimental peaks with the theoretical ones"
    window   = 10.
    lastpeak = True
    @initdefaults
    def __init__(self, **kwa):
        super().__init__(**kwa)

    def __call__(self, peaks:np.ndarray, stretch = 1., bias = 0.) -> PEAKS_TYPE:
        hpin           = self.peaks if self.lastpeak else self.peaks[:-1]
        ided           = np.full((len(peaks),), np.NaN, dtype = PEAKS_DTYPE)
        ided['zvalue'] = peaks

        if len(peaks) > 0 and len(hpin) > 0:
            peaks = stretch*peaks+bias-(stretch*peaks[0]+bias)
            ids   = _match.compute(hpin, peaks, self.window)
            ided['key'][ids[:,1]] = hpin[ids[:,0]]
        return ided
