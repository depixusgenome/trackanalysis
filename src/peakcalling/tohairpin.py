#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Matching experimental peaks to hairpins
"""
from   typing       import Dict, Sequence, Iterator, Tuple, Any, Union, cast
import numpy        as np

from utils          import StreamUnion, initdefaults
from sequences      import read as _read, peaks as _peaks
from ._core         import cost as _cost, match as _match # pylint: disable=import-error
from ._base         import (Distance, GriddedOptimization, PointwiseOptimization,
                            DEFAULT_BEST)

class HairpinFitter:
    "Class containing theoretical peaks and means for matching them to experimental ones"
    peaks     = np.empty((0,), dtype = 'f4') # type: np.array
    firstpeak = True
    lastpeak  = False
    @initdefaults(frozenset(locals()))
    def __init__(self, **kwa):
        pass

    @property
    def expectedpeaks(self):
        "returns the peaks +- the hairpin extension"
        return self.peaks[None if self.firstpeak else 1:None if self.lastpeak  else -1]

    @property
    def hybridizations(self):
        "returns only peaks linked to hibridizations"
        return self.peaks[1:-1]

    @staticmethod
    def topeaks(seq:str, oligos:Sequence[str]) -> np.ndarray:
        "creates a peak sequence from a dna sequence and a list of oligos"
        return np.pad(np.array(_peaks(seq, oligos)['position'], dtype = 'i4'),
                      1, 'constant', constant_values = (0, len(seq)))

    @classmethod
    def read(cls, path:Union[StreamUnion, Dict], oligos:Sequence[str], **kwa
            ) -> Iterator[Tuple[str, 'HairpinFitter']]:
        "creates a list of *HairpinFitter* from a fasta file and a list of oligos"
        itr = (path         if isinstance(path, Iterator)             else
               path.items() if callable(getattr(path, 'items', None)) else # type: ignore
               _read(path))
        itr = cast(Iterator[Tuple[str,Any]], itr)
        return ((name, cls(**kwa, peaks = cls.topeaks(seq, oligos))) for name, seq in itr)

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

class GaussianProductFit(HairpinFitter, GriddedOptimization):
    """
    Matching experimental peaks to hairpins using a cost function:

    If:

        R(X, Y) = Σ_{i, j} exp(-((x_i -y_j)/σ)²)


    Then the cost is:

        1 - R(X, Y)/sqrt(R(X, X) R(Y, Y))
    """
    precision = 15.
    def __init__(self, **kwa):
        HairpinFitter.__init__(self, **kwa)
        GriddedOptimization.__init__(self, **kwa)

    def optimize(self, peaks: np.ndarray) -> Distance:
        "optimizes the cost function"
        best  = DEFAULT_BEST, self.stretch.center, (self.bias.center or 0.)
        delta = 0.
        if len(peaks) > 1:
            rng   = lambda x, y, z: (('min_'+x, y-z), (x, y), ('max_'+x, y+z))
            brng  = lambda w, x, y, z: rng(w, x[0]*(x[1]+y), z*x[0])
            args  = self.optimconfig(symmetry = self.symmetry, noise = self.precision)

            hpin  = self.expectedpeaks
            delta = peaks[0]
            peaks = (peaks - peaks[0])[None if self.firstpeak else 1:]
            for vals in self.grid:
                args.update(rng('stretch', vals[0], self.stretch.step))
                if self.bias.center is None:
                    args.update(brng('bias', vals, 0.,    self.bias.step))
                else:
                    args.update(brng('bias', vals, delta, self.bias.step))
                try:
                    out = _cost.optimize(hpin, peaks, **args)
                except: # pylint: disable=bare-except
                    continue
                else:
                    if out[0] < best[0]:
                        best = out

        return Distance(best[0], best[1], delta-best[2]/best[1])

    def value(self, peaks: np.ndarray, stretch, bias) -> Tuple[float, float, float]:
        "computes the cost value at a given stretch and bias as well as derivates"
        if len(peaks) == 0:
            return 0., 0., 0.
        hpin  = self.expectedpeaks
        peaks = (peaks - peaks[0])[None if self.firstpeak else 1:]
        if any(isinstance(i, (Sequence, np.ndarray)) for i in (stretch, bias)):
            stretch = np.asarray(stretch)
            bias    = -np.asarray(bias)*stretch
            fcn     = lambda i, j: _cost.compute(hpin, peaks,
                                                 symmetry = self.symmetry,
                                                 noise    = self.precision,
                                                 stretch  = i, bias     = j),
            ufcn    = np.frompyfunc(fcn, 2, 3)
            return ufcn(stretch, bias)
        return _cost.compute(hpin, peaks,
                             symmetry = self.symmetry,
                             noise    = self.precision,
                             stretch  = stretch,
                             bias     = -bias*stretch)

PEAKS_DTYPE = np.dtype([('zvalue', 'f4'), ('key', 'i4')])
PEAKS_TYPE  = Union[Sequence[Tuple[float,int]],np.ndarray]
class PeakMatching(HairpinFitter, PointwiseOptimization):
    "Identifying experimental peaks with the theoretical ones"
    window          = 10.
    lastpeak        = True
    bases           = (20, 20)
    dataprecisions  = 1., 1e-3
    @initdefaults(frozenset(locals()))
    def __init__(self, **kwa):
        HairpinFitter.__init__(self, **kwa)
        PointwiseOptimization.__init__(self, **kwa)

    @property
    def expectedpeaks(self):
        "returns the peaks +- the hairpin extension"
        return self.peaks if self.lastpeak else self.peaks[:-1]

    def pair(self, peaks:np.ndarray, stretch = 1., bias = 0.) -> PEAKS_TYPE:
        "returns experimental peaks paired to the theory"
        hpin           = self.expectedpeaks
        ided           = np.empty((len(peaks),), dtype = PEAKS_DTYPE)
        ided['zvalue'] = peaks
        ided['key']    = np.iinfo('i4').min

        if len(peaks) > 0 and len(hpin) > 0:
            peaks = stretch*(peaks-bias)
            ids   = _match.compute(hpin, peaks, self.window)
            ided['key'][ids[:,1]] = np.int32(hpin[ids[:,0]]) # type: ignore
        return ided

    def nfound(self, peaks:np.ndarray, stretch = 1., bias = 0.) -> int:
        "returns the number of paired peaks"
        hpin = self.expectedpeaks
        if len(peaks) > 0 and len(hpin) > 0:
            peaks = stretch*(peaks-bias)
            return _match.nfound(hpin, peaks, self.window)
        return 0

    def distance(self, peaks:np.ndarray,
                 stretch = 1., bias = 0.) -> Tuple[int, float, float, int]:
        """
        Computes the square of the distance between matched peaks,
        allowing a maximum distance of *sigma* to a match.

        Outputs a tuple with:

            1. Σ_{paired} (x_i - y_i)² / (σ²  N) + len(reference) + len(experiment) - 2*N
            2. stretch gradient
            3. bias gradient
            4. N: number of paired peaks
        """

        hpin = self.expectedpeaks
        return _match.distance(hpin, peaks, self.window, stretch, -bias*stretch)

    def optimize(self, peaks:np.ndarray) -> Distance:
        "Optimizes the distance"
        best  = DEFAULT_BEST, self.stretch.center, (self.bias.center or 0.)
        if len(peaks) > 1:
            rng   = lambda x, y, z: (('min_'+x, y-z), (x, y), ('max_'+x, y+z))
            args  = self.optimconfig(window = self.window)
            hpin  = self.expectedpeaks
            pots  = {i: self.distance(peaks, *i)[-1]
                     for i in self.pointgrid(self.peaks, peaks)}
            maxi  = max(pots.values(), default = DEFAULT_BEST)-1 # type: ignore
            good  = set((int(i[0]/self.dataprecisions[0]), int(i[1]/self.dataprecisions[1]))
                        for i, j in pots.items() if j >= maxi)
            for ivals in good:
                vals = ivals[0]*self.dataprecisions[0], ivals[1]*self.dataprecisions[1]
                args.update(rng('stretch',  vals[0],         self.stretch.step))
                args.update(rng('bias',    -vals[0]*vals[1], self.bias.step*vals[0]))
                try:
                    out = _match.optimize(hpin, peaks, **args)
                except: # pylint: disable=bare-except
                    continue
                else:
                    if out[0] < best[0]:
                        best = out

        return Distance(best[0], best[1], -best[2]/best[1])
