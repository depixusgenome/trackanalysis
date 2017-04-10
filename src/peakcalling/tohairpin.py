#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"""
Matching experimental peaks to hairpins
"""
from   typing       import (Dict, Sequence, NamedTuple, # pylint: disable=unused-import
                            Callable, Iterator, Iterable, Tuple, Any,
                            Optional, Union, cast)
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
                                [('center', Optional[float]),
                                 ('size',   float),
                                 ('step',   float)])

class Hairpin:
    u"Matching experimental peaks to hairpins"
    peaks    = np.empty((0,), dtype = 'f4') # type: np.array
    lastpeak = False
    @initdefaults
    def __init__(self, **kwa):
        pass

    @property
    def hybridizations(self):
        "returns only peaks linked to hibridizations"
        return self.peaks[1:-1]

    @staticmethod
    def topeaks(seq:str, oligos:Sequence[str]) -> np.ndarray:
        u"creates a peak sequence from a dna sequence and a list of oligos"
        return np.pad(np.array(_peaks(seq, oligos)['position'], dtype = 'i4'),
                      1, 'constant', constant_values = (0, len(seq)))

    @classmethod
    def read(cls, path:StreamUnion, oligos:Sequence[str]) -> 'Iterator[Tuple[str,Hairpin]]':
        u"creates a list of *Hairpin* from a fasta file and a list of oligos"
        return ((name, cls(peaks = cls.topeaks(seq, oligos)))
                for name, seq in _read(path))

Distance = NamedTuple('Distance', [('value', float), ('stretch', float), ('bias', float)])

class HairpinDistance(Hairpin):
    u"Matching experimental peaks to hairpins"
    DEFAULT_BEST = 1e20
    symmetry     = False
    precision    = 15.
    stretch      = Range(1./8.8e-4, 200., 100.)
    bias         = Range(None,       20.,  20.)
    optim        = OptimisationParams(1e-4, 1e-8, 1e-4, 1e-8, 100)
    @initdefaults
    def __init__(self, **kwa):
        super().__init__(**kwa)

    def arange(self, attr: Optional[str] = None
              ) -> Union[np.ndarray, Iterator[Tuple[float, ...]]]:
        "returns the range on which the attribute is explored"
        if attr is None:
            return product(self.arange('stretch'), self.arange('bias'))

        val = getattr(self, attr)
        if val.center is None:
            return np.arange(-val.size, val.size+val.step*.1, val.step)
        return np.arange(val.center-val.size, val.center+val.size+val.step*.1, val.step)

    @kwargsdefaults
    def __call__(self, peaks : np.ndarray) -> Distance:
        best  = self.DEFAULT_BEST, self.stretch.center, (self.bias.center or 0.)
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
            for vals in self.arange():
                args.update(rng('stretch', vals[0], self.stretch.step))
                if self.bias.center is None:
                    args.update(rng('bias', vals[1], self.bias.step))
                else:
                    args.update(rng('bias', vals[1]+delta*vals[0], self.bias.step))
                try:
                    out = optimize(hpin, peaks, **args)
                except: # pylint: disable=bare-except
                    continue
                else:
                    if out[0] < best[0]:
                        best = out

        return Distance(best[0], best[1], delta-best[2]/best[1])

    @staticmethod
    def silhouette(dist, key = None) -> float:
        "returns the silhouette value for a given key"
        if len(dist) > 1:
            if key is None:
                key = min(dist, key = dist.__getitem__)
            aval = dist[key].value
            bval = min(i[0] for k, i in dist.items() if k != key)
            return ((bval-aval)/max(aval, bval)-.5)*2.
        else:
            return 1. if len(dist) == 1 else -3.

PEAKS_DTYPE = np.dtype([('zvalue', 'f4'), ('key', 'i4')])
PEAKS_TYPE  = Union[Sequence[Tuple[float,int]],np.ndarray]
class PeakIdentifier(Hairpin):
    u"Identifying experimental peaks with the theoretical ones"
    window   = 10.
    lastpeak = True
    @initdefaults
    def __init__(self, **kwa):
        super().__init__(**kwa)

    def __call__(self, peaks:np.ndarray, stretch = 1., bias = 0.) -> PEAKS_TYPE:
        hpin           = self.peaks if self.lastpeak else self.peaks[:-1]
        ided           = np.empty((len(peaks),), dtype = PEAKS_DTYPE)
        ided['zvalue'] = peaks
        ided['key']    = np.iinfo('i4').min

        if len(peaks) > 0 and len(hpin) > 0:
            peaks = stretch*peaks+bias-(stretch*peaks[0]+bias)
            ids   = _match.compute(hpin, peaks, self.window)
            ided['key'][ids[:,1]] = np.int32(hpin[ids[:,0]]) # type: ignore
        return ided
