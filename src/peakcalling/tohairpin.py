#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Matching experimental peaks to hairpins
"""
from   typing       import Dict, Sequence, Iterator, Tuple, Any, Union, cast
from   functools    import partial
from   itertools    import product
import numpy        as     np

from utils          import StreamUnion, initdefaults
from sequences      import read as _read, peaks as _peaks
from ._core         import cost as _cost, match as _match # pylint: disable=import-error
from ._base         import (Distance, GriddedOptimization, PointwiseOptimization,
                            DEFAULT_BEST, OptimizationParams, Symmetry,
                            chisquare, chisquarevalue)

class HairpinFitter(OptimizationParams):
    "Class containing theoretical peaks and means for matching them to experimental ones"
    peaks     = np.empty((0,), dtype = 'f4') # type: np.array
    firstpeak = True
    lastpeak  = False
    @initdefaults(frozenset(locals()))
    def __init__(self, **kwa):
        super().__init__(**kwa)

    @property
    def expectedpeaks(self) -> np.ndarray:
        "returns the peaks +- the hairpin extension"
        pks = self.peaks[None if self.firstpeak else 1:None if self.lastpeak  else -1]
        return np.asarray(pks)

    @property
    def hybridizations(self) -> np.ndarray:
        "returns only peaks linked to hibridizations"
        return np.asarray(self.peaks[1:-1])

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

    def optimize(self, peaks: np.ndarray) -> Distance:
        "optimizes the cost function"
        raise NotImplementedError()

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
        peaks = np.asarray(peaks)
        best  = DEFAULT_BEST, self.stretch.center, (self.bias.center or 0.)
        delta = 0.
        if len(peaks) > 1:
            rng   = lambda x, y, z: (('min_'+x, y-z), (x, y), ('max_'+x, y+z))
            brng  = lambda w, x, y, z: rng(w, x[0]*(x[1]+y), z*x[0])
            args  = self.optimconfig(symmetry = self.symmetry is Symmetry.both,
                                     noise = self.precision)

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
                    out = self._optimize(hpin, peaks, args)
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
            fcn     = lambda i, j: self._value(hpin, peaks, i, j,
                                               symmetry = self.symmetry is Symmetry.both,
                                               noise    = self.precision)
            ufcn    = np.frompyfunc(fcn, 2, 3)
            return ufcn(stretch, bias)
        return self._value(hpin, peaks, stretch, -bias*stretch,
                           symmetry = self.symmetry is Symmetry.both,
                           noise    = self.precision)

    @staticmethod
    def _value(hpin: np.ndarray, peaks: np.ndarray, stretch:float, bias:float, **_):
        return _cost.compute(hpin, peaks, stretch = stretch, bias = bias, **_)

    @staticmethod
    def _optimize(hpin, peaks, args):
        return _cost.optimize(hpin, peaks, **args)

class ChiSquareFit(GaussianProductFit):
    """
    We use the GaussianProductFit results to match peaks then estimate
    the best Χ² fit between matched peaks, adding their count as well.
    """
    symmetry = Symmetry.right
    window   = 10.
    def _optimalvalue(self, hpin: np.ndarray, peaks: np.ndarray, # type: ignore
                      stretch:float, bias:float, **_):
        sym = Symmetry.both if self.symmetry is Symmetry.both else Symmetry.left
        return chisquare(hpin, peaks, self.firstpeak, sym, self.window, stretch, bias)

    def _value(self, hpin: np.ndarray, peaks: np.ndarray, # type: ignore
               stretch:float, bias:float, **_):
        sym = Symmetry.both if self.symmetry is Symmetry.both else Symmetry.left
        return chisquarevalue(hpin, peaks, self.firstpeak, sym, self.window, stretch, bias)

    def _optimize(self, hpin, peaks, args):
        "optimizes the cost function"
        pars = _cost.optimize(hpin, peaks, **args)
        return self._optimalvalue(hpin, peaks, pars[1], pars[2])

    def optimize(self, peaks: np.ndarray) -> Distance:
        "optimizes the cost function"
        peaks = np.asarray(peaks)
        ret   = super().optimize(peaks)
        if self.symmetry is Symmetry.right:
            hpin = self.expectedpeaks
            return Distance(chisquarevalue(hpin, (peaks-ret[2])*ret[1], self.firstpeak,
                                           self.symmetry, self.window, 1., 0.)[0],
                            ret[1], ret[2])
        return ret

class PeakGridFit(HairpinFitter):
    """
    Fit to one or two lists of reference peaks.

    The concept is to consider over all associations of a reference peak with an
    experimental peak and to iterate over pairs of such associations.

    For each of these pairs:

    * we estimate a stretch and bias using these 2 pairs
    * we match the reference to the experiment using this estimation
    * we re-estimate a stretch and bias using this match
    * we estimate a reduced χ² as the cost function

    The stretch & bias with the least χ² value is returned.
    """
    window    = 10.
    symmetry  = Symmetry.left
    firstpeak = False
    lastpeak  = False
    DEFAULT   = Distance(DEFAULT_BEST, 1./8.8e-4, 0.)
    def optimize(self, peaks:np.ndarray) -> Distance:
        "computes stretch and bias for potential pairings"
        peaks = np.asarray(peaks)
        if len(peaks) < 2:
            return self.DEFAULT

        rng   = lambda val: ((val.center if val.center else 0.) - val.size,
                             (val.center if val.center else 0.) + val.size)
        args  = rng(self.stretch)+rng(self.bias)
        centr = sum(args[:2])*.5, sum(args[2:])*.5
        if len(peaks) < 2:
            return Distance(DEFAULT_BEST, *centr)

        delta = peaks[0] if self.bias.center is None else 0.
        if delta != 0.:
            peaks = peaks - delta

        ref   = self.expectedpeaks
        itr   = tuple(i for i in _match.PeakIterator(ref, peaks, *args)) + (centr,)
        args  = ref, peaks, False, self.symmetry, self.window
        minv  = min(chisquare(*args, stretch, -stretch*bias) for stretch, bias in itr)

        return Distance(minv[0], minv[1], delta-minv[2]/minv[1])

    def value(self, peaks:np.ndarray,
              stretch: Union[float, np.ndarray],
              bias:    Union[float, np.ndarray]) -> float:
        "computes the cost value at a given stretch and bias"
        np.seterr(under = "ignore")
        left  = self.expectedpeaks
        fcn   = partial(self._cost_function, left, peaks)
        if any(isinstance(i, (np.ndarray, Sequence)) for i in  (stretch, bias)):
            bias = np.asarray(bias)-peaks.minv+left.minv/np.asarray(stretch)
            ufcn = np.frompyfunc(fcn, 2, 1)
            return ufcn(stretch, bias)
        return fcn(stretch, bias-peaks.minv+left.minv/stretch)

    def _cost_function(self, left, right, stretch: float, bias: float):
        return chisquarevalue(left, right,
                              False, self.symmetry, self.window,
                              stretch, -stretch*bias)[0]

class EdgePeaksGridFit(HairpinFitter):
    """
    Fit to two lists of reference peaks.

    # Consider one list of reference peaks

    The concept is to consider over all associations of a reference peak with an
    experimental peak and to iterate over pairs of such associations.

    For each of these pairs:

    * we estimate a stretch and bias using these 2 pairs
    * we match the reference to the experiment using this estimation
    * we re-estimate a stretch and bias using this match
    * we estimate a reduced χ² as the cost function

    The stretch & bias with the least χ² value is returned.

    # With two lists of reference peaks

    The same idea is used except that the 1st list is fit to the bottom peaks
    and the 2nd is fit to the top peaks. The fit is actually performed over both
    lists at the same time using a single stretch value but allowing a different
    bias for top and bottom. The χ² is estimated over both lists.

    The cost function is, where *i* iterates over lists of peaks and *j* over
    elements in that list:

        F(x, y) = Σ_{ij} (y_{ij} - a x_{ij} -b_i) **2

    thus:

        ∂_a  F   = 0 ⇔  0 = Σ_{ij} x_{ij} (y_{ij} - a x_{ij} -b_i)
        ∂_{b_i}F = 0 ⇔  0 = Σ_j (y_{ij} - a x_{ij} -b_i)

    and:
        b_i = <y>_i - a <x>_i
        a   = (<xy> - Σ_i N_i/N <x>_i <y>_i) / (<x²> - Σ_i N_i/N (<x>_i)²)

    We also have, if δx = σ:

        δa  = a∙σ/N∙√(Σ_{ij}((y_ij - <y>_i)/U -2 (x_{ij} - <x>_i)/V)²)

    where:
        a   = U/V
    """
    window    = 10.
    symmetry  = Symmetry.left
    firstpeak = False
    lastpeak  = False
    DEFAULT   = Distance(DEFAULT_BEST, 1./8.8e-4, cast(float, (0., 0.)))
    def optimize(self, peaks:np.ndarray) -> Distance:
        "computes stretch and bias for potential pairings"
        rng  = lambda val: ((val.center if val.center else 0.) - val.size,
                            (val.center if val.center else 0.) + val.size)
        bias, stretch = rng(self.bias), rng(self.stretch)


        if len(self.peaks) > 2:
            raise NotImplementedError()

        extr = [(i[-1]-i[0])/stretch[0]+bias[1] for i in self.peaks]
        pks  = [np.asarray(peaks[:np.searchsorted(peaks, peaks[0]+extr[0])]),
                np.asarray(peaks[np.searchsorted(peaks,  peaks[-1]-extr[1]):])
               ]
        if any(len(i) < 2 for i in pks):
            return self.DEFAULT

        args = stretch + (-np.finfo('f4').max, np.finfo('f4').max) + (True,)
        itrs = [tuple(np.copy(i) for i in _match.PeakIterator(ref, item, *args))
                for ref, item in zip(self.peaks, pks)]

        nref = sum(len(i) for i in self.peaks)
        minv = min((self.__chisquare(nref, pks, inds) for inds in product(*itrs)),
                   default = self.DEFAULT)
        return Distance(minv[0], minv[1], -(np.asarray(minv[2])/minv[1]))

    def value(self, peaks:np.ndarray,
              stretch: Union[float, np.ndarray],
              bias:    Union[float, np.ndarray]) -> float:
        "computes the cost value at a given stretch and bias"
        np.seterr(under = "ignore")
        left  = self.expectedpeaks
        fcn   = partial(self._cost_function, left, peaks)
        if any(isinstance(i, (np.ndarray, Sequence)) for i in  (stretch, bias)):
            bias = np.asarray(bias)-peaks.minv+left.minv/np.asarray(stretch)
            ufcn = np.frompyfunc(fcn, 2, 1)
            return ufcn(stretch, bias)
        return fcn(stretch, bias-peaks.minv+left.minv/stretch)

    def _cost_function(self, left, right, stretch: float, bias: float):
        return chisquarevalue(left, right,
                              False, self.symmetry, self.window,
                              stretch, -stretch*bias)[0]

    def __selection(self, peaks:Sequence[np.ndarray], inds: Sequence[np.ndarray]):
        return ([i[j[:,0]] for i, j in zip(self.peaks, inds)],
                [i[j[:,1]] for i, j in zip(peaks,      inds)])

    def __params(self, peaks: Sequence[np.ndarray], inds: Sequence[np.ndarray]):
        """
        we have:
                F(x, y) = Σ_{ij} (y_{ij} - a x_{ij} -b_i) **2

        with:
            d/da   = 0 = Σ_{ij} x_{ij} (y_{ij} - a x_{ij} -b_i)
            d/db_i = 0 = Σ_j (y_{ij} - a x_{ij} -b_i)

        thus:
            b_i = <y>_i - a <x>_i
            a   = (<xy> - Σ_i N_i/N <x>_i <y>_i) / (<x²> - Σ_i N_i/N (<x>_i)²)

        We also have, if δx = σ:

            δa  = sqrt(Σ_{ij}((da/dx_{ij})²)) σ
            δa  = sqrt((Σ_{ij}((y_ij - <y>_i)/(<x²> - Σ_i N_i/N (<x>_i)²)
                                -((<xy> - Σ_i N_i/N <x>_i <y>_i)
                                  2 (x_{ij} - Σ_i <x>_i)
                                 /(<x²> - Σ_i N_i/N (<x>_i)²)²))) σ/N
        """
        refs, pks = self.__selection(peaks, inds)
        xyv  = sum((i*j) .sum()             for i, j in zip(refs, pks))
        xyv -= sum(i.mean()*j.mean()*len(i) for i, j in zip(refs, pks))

        x2v  = sum((i**2).sum()       for i in pks)
        x2v -= sum(i.mean()**2*len(i) for i in pks)

        stretch = xyv/x2v
        biases  = [j.mean()-i.mean()*stretch for i, j in zip(pks, refs)]
        return stretch, biases

    def __chisquare(self,
                    npeaksexpected: int,
                    peaks:          Sequence[np.ndarray],
                    indexes:        Sequence[np.ndarray]):
        if any(len(i) == 0 for i in indexes):
            return self.DEFAULT
        stretch, biases = self.__params(peaks, indexes)

        inds = [_match.compute(i, j*stretch+bias, self.window)
                for i, j, bias in zip(self.peaks, peaks, biases)]
        if any(len(i) == 0 for i in inds):
            return self.DEFAULT
        stretch, biases = self.__params(peaks, inds)

        inds = [_match.compute(i, j*stretch+bias, self.window)
                for i, j, bias in zip(self.peaks, peaks, biases)]
        chi2 = sum(((i-stretch*j-bias)**2).sum()
                   for i, j, bias in zip(*self.__selection(peaks, inds),
                                         biases))/self.window**2

        chi2 += (npeaksexpected-sum(len(i) for i in inds))**2
        return np.sqrt(max(0., chi2)/npeaksexpected), stretch, biases

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
