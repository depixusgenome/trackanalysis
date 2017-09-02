#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Matching experimental peaks to hairpins
"""
from   typing       import (Dict, Sequence, NamedTuple, # pylint: disable=unused-import
                            Callable, Iterator, Iterable, Tuple, Any,
                            Optional, Union, cast)
from   itertools    import product
import numpy        as np

from utils          import StreamUnion, kwargsdefaults, initdefaults
from sequences      import read as _read, peaks as _peaks
from ._core         import cost as _cost, match as _match # pylint: disable=no-name-in-module

OptimisationParams = NamedTuple('OptimisationParams',
                                [('threshold_param_rel', float),
                                 ('threshold_param_abs', float),
                                 ('threshold_func_rel',  float),
                                 ('stopval',             float),
                                 ('maxeval',             int)])
def _dict(cnf:OptimisationParams, **kwa) -> dict:
    kwa.update(threshold_param_rel = cnf[0], # type: ignore
               threshold_param_abs = cnf[1],
               threshold_func_rel  = cnf[2],
               stopval             = cnf[3],
               maxeval             = cnf[4])
    return kwa


Range              = NamedTuple('Range',
                                [('center',  Optional[float]),
                                 ('size',    float),
                                 ('step',    float)])

Distance           = NamedTuple('Distance',
                                [('value',   float),
                                 ('stretch', float),
                                 ('bias',    float)])

class Hairpin:
    "Class containing theoretical peaks and means for matching them to experimental ones"
    DEFAULT_BEST = 1e20
    peaks        = np.empty((0,), dtype = 'f4') # type: np.array
    lastpeak     = False
    _KEYS        = frozenset(locals())
    @initdefaults(_KEYS)
    def __init__(self, **kwa):
        pass

    @property
    def expectedpeaks(self):
        "returns the peaks +- the hairpin extension"
        return self.peaks if self.lastpeak else self.peaks[:-1]

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
            ) -> 'Iterator[Tuple[str,Hairpin]]':
        "creates a list of *Hairpin* from a fasta file and a list of oligos"
        itr = (path         if isinstance(path, Iterator)               else
               path.items() if callable(getattr(path, 'items', None))   else
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

class HairpinDistance(Hairpin):
    """
    Matching experimental peaks to hairpins using a cost function:

    If:

        R(X, Y) = Σ_{i, j} exp(-((x_i -y_j)/σ)²)


    Then the cost is:

        1 - R(X, Y)/sqrt(R(X, X) R(Y, Y))
    """
    symmetry  = False
    precision = 15.
    stretch   = Range(1./8.8e-4, 200., 100.)
    bias      = Range(None,       20.*8.8e-4, 20.*8.8e-4)
    optim     = OptimisationParams(1e-4, 1e-8, 1e-4, 1e-8, 100)
    __KEYS    = frozenset(locals())
    @initdefaults(__KEYS)
    def __init__(self, **kwa):
        super().__init__(**kwa)

    @kwargsdefaults(__KEYS)
    def optimize(self, peaks: np.ndarray) -> Distance:
        "optimizes the cost function"
        best  = self.DEFAULT_BEST, self.stretch.center, (self.bias.center or 0.)
        delta = 0.
        if len(peaks) > 1:
            rng   = lambda x, y, z: (('min_'+x, y-z), (x, y), ('max_'+x, y+z))
            brng  = lambda w, x, y, z: rng(w, x[0]*(x[1]+y), z*x[0])
            args  = _dict(self.optim, symmetry = self.symmetry, noise = self.precision)

            hpin  = self.expectedpeaks
            delta = peaks[0]
            peaks = peaks - peaks[0]
            for vals in self.__arange():
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

    @kwargsdefaults(__KEYS)
    def value(self, peaks: np.ndarray, stretch, bias) -> Tuple[float, float, float]:
        "computes the cost value at a given stretch and bias as well as derivates"
        if len(peaks) == 0:
            return 0., 0., 0.
        hpin = self.expectedpeaks
        return _cost.compute(hpin, peaks - peaks[0],
                             symmetry = self.symmetry,
                             noise    = self.precision,
                             stretch  = stretch,
                             bias     = (peaks[0]-bias)*stretch)

    def __arange(self, attr: Optional[str] = None
                ) -> Union[np.ndarray, Iterator[Tuple[float, ...]]]:
        "returns the range on which the attribute is explored"
        if attr is None:
            return product(self.__arange('stretch'), self.__arange('bias'))

        val = getattr(self, attr)
        cnt = max(1, (int(2.*val.size/val.step+0.5)//2)*2+1)
        if cnt == 1:
            return np.array([0. if val.center is None else val.center], dtype = 'f4')
        if val.center is None:
            return np.linspace(-val.size, val.size, cnt)
        return np.linspace(val.center-val.size, val.center+val.size, cnt)

PEAKS_DTYPE = np.dtype([('zvalue', 'f4'), ('key', 'i4')])
PEAKS_TYPE  = Union[Sequence[Tuple[float,int]],np.ndarray]
class PeakIdentifier(Hairpin):
    "Identifying experimental peaks with the theoretical ones"
    window       = 10.
    lastpeak     = True
    bases        = (20, 20)
    stretch      = Range(1./8.8e-4, 200., 50.)
    bias         = Range(None,       20.*8.8e-4, 20.*8.8e-4)
    optim        = OptimisationParams(1e-4, 1e-8, 1e-4, 1e-8, 100)
    _precision   = 1., 1e-3
    __KEYS       = frozenset(locals())
    @initdefaults(__KEYS)
    def __init__(self, **kwa):
        super().__init__(**kwa)

    @property
    def expectedpeaks(self):
        "returns the peaks +- the hairpin extension"
        return self.peaks if self.lastpeak else self.peaks[:-1]

    @kwargsdefaults(__KEYS)
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

    @kwargsdefaults(__KEYS)
    def nfound(self, peaks:np.ndarray, stretch = 1., bias = 0.) -> int:
        "returns the number of paired peaks"
        hpin = self.expectedpeaks
        if len(peaks) > 0 and len(hpin) > 0:
            peaks = stretch*(peaks-bias)
            return _match.nfound(hpin, peaks, self.window)
        return 0

    @kwargsdefaults(__KEYS)
    def distance(self, peaks:np.ndarray, stretch = 1., bias = 0.) -> int:
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

    @kwargsdefaults(__KEYS)
    def optimize(self, peaks:np.ndarray) -> Distance:
        "Optimizes the distance"
        best  = self.DEFAULT_BEST, self.stretch.center, (self.bias.center or 0.)
        if len(peaks) > 1:
            rng   = lambda x, y, z: (('min_'+x, y-z), (x, y), ('max_'+x, y+z))
            args  = _dict(self.optim, window = self.window)
            hpin  = self.expectedpeaks
            pots  = {i: self.distance(peaks, *i)[-1] for i in self.__arange(peaks)}
            maxi  = max(pots.values(), default = self.DEFAULT_BEST)-1
            good  = set((int(i[0]/self._precision[0]), int(i[1]/self._precision[1]))
                        for i, j in pots.items() if j >= maxi)
            for ivals in good:
                vals = ivals[0]*self._precision[0], ivals[1]*self._precision[1]
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

    def __arange(self, exp:np.ndarray) -> Iterator[Tuple[float, float]]:
        "computes stretch and bias for potential pairings"
        ref        = self.peaks
        minstretch = self.stretch.center - self.stretch.size
        maxstretch = self.stretch.center + self.stretch.size
        if self.bias.center is None:
            minbias, maxbias = -1e5, 1e5
        else:
            minbias = self.bias.center - self.bias.size
            maxbias = self.bias.center + self.bias.size

        basemax = self.peaks[-1] + self.bases[1]
        zeromin = self.peaks[0]  - self.bases[0]
        zeromax = self.peaks[0]  + self.bases[0]
        def _compute(iref, jref, iexp, jexp):
            rho  = (ref[iref]-ref[jref])/(exp[iexp] - exp[jexp])
            return rho, exp[iexp]-ref[iref]/rho

        pot = iter(_compute(iref, jref, iexp, jexp)
                   for iref in range(len(ref)-1)
                   for jref in range(iref+1, len(ref))
                   for iexp in range(len(exp)-1)
                   for jexp in range(iexp+1, len(exp)))
        valid = set((int(val[0]/self._precision[0]+0.5),
                     int(val[1]/self._precision[1]+0.5)) for val in pot
                    if (minstretch  <= val[0] <= maxstretch
                        and minbias <= val[1] <= maxbias
                        and val[0]*(exp[-1]-val[1]) <= basemax
                        and zeromin <= val[0]*(exp[0] -val[1]) <= zeromax
                       ))
        return iter((val[0]*self._precision[0], val[1]*self._precision[1])
                    for val in valid)
