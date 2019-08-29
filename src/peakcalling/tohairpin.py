#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Matching experimental peaks to hairpins
"""
from   copy         import copy
from   functools    import partial
from   itertools    import product
from   typing       import Dict, List, Sequence, Iterator, Tuple, Any, Union, cast
import numpy        as     np

from utils          import StreamUnion, initdefaults
from sequences      import read as _read, peaks as _peaks
from .chisquare     import ChiSquare
from ._base         import (Distance, GriddedOptimization, PointwiseOptimization,
                            OptimizationParams, Symmetry, Pivot, Range)
from ._core         import cost as _cost, match as _match # pylint: disable=import-error

class HairpinFitter(OptimizationParams):
    "Class containing theoretical peaks and means for matching them to experimental ones"
    peaks:      np.ndarray = np.empty((0,), dtype = 'f4')
    pivot:      Pivot      = Pivot.bottom
    strandsize: int        = 0

    def __delayed_init__(self, _):
        self.peaks = np.asarray(self.peaks, dtype = "f4")
        for i in ('stretch', 'bias'):
            val = getattr(self, i)
            if not isinstance(val, Range):
                setattr(self, i, Range(**val) if isinstance(val, dict) else Range(*val))

    @initdefaults(frozenset(locals()))
    def __init__(self, **kwa):
        super().__init__(**kwa)

    @property
    def hasbaseline(self) -> bool:
        "whether z = 0 is in peaks"
        return len(self.peaks) > 0 and self.peaks[0] == 0

    @property
    def hassinglestrand(self) -> bool:
        "whether z = 0 is in peaks"
        return len(self.peaks) > 0 and self.peaks[-1] == self.strandsize

    @staticmethod
    def topeaks(seq:str, oligos:Sequence[str]) -> np.ndarray:
        "creates a peak sequence from a dna sequence and a list of oligos"
        return np.array(_peaks(seq, oligos)['position'], dtype = 'i4')

    @classmethod
    def read(cls, path:Union[StreamUnion, Dict], oligos:Sequence[str], **kwa
            ) -> Iterator[Tuple[str, 'HairpinFitter']]:
        "creates a list of *HairpinFitter* from a fasta file and a list of oligos"
        itr   = (path         if isinstance(path, Iterator)             else
                 path.items() if callable(getattr(path, 'items', None)) else # type: ignore
                 _read(path))

        for name, seq in cast(Iterator[Tuple[str,Any]], itr):
            self = cls(**kwa,
                       peaks      = cls.topeaks(seq, oligos),
                       strandsize = len(seq))
            yield (name, self)

    @staticmethod
    def silhouette(dist, key = None) -> float:
        "returns the silhouette value for a given key"
        if len(dist) > 1:
            if key is None:
                key = min(dist, key = dist.__getitem__)
            aval = dist[key].value
            bval = min(i[0] for k, i in dist.items() if k != key)
            return ((bval-aval)/max(aval, bval)-.5)*2.
        return 1. if len(dist) == 1 else -3.

    def withinrange(self, extension) -> bool:
        "return whether the bead extension is within range of the last peak (hairpin size)"
        if self.strandsize == 0:
            return True
        if len(self.peaks) == 0:
            return False
        mins = (self.stretch.center or self.defaultstretch) - self.stretch.size
        maxs = (self.stretch.center or self.defaultstretch) + self.stretch.size
        minb = (self.bias.center or 0.) - self.bias.size
        maxb = (self.bias.center or 0.) + self.bias.size
        return (extension-maxb)*mins < self.strandsize < (extension-minb)*maxs

    def defaultparameters(self):
        "return the default parameters"
        return Distance(np.finfo("f4").max, self.defaultstretch, 0.)

    def optimizewithinrange(self, peaks: np.ndarray, extent:float) -> Distance:
        "optimizes the cost function if the extension is within range"
        if self.withinrange(extent):
            return self.optimize(peaks)
        return self.defaultparameters()

    def optimize(self, peaks: np.ndarray) -> Distance:
        "optimizes the cost function"
        raise NotImplementedError()

    def _applypivot(self, peaks: np.ndarray) -> Tuple[float, np.ndarray, float, np.ndarray]:
        if len(peaks) < 2:
            return 0., [], 0., []

        delta = (peaks[0] if self.pivot == Pivot.bottom   else
                 0        if self.pivot == Pivot.absolute else
                 peaks[-1])
        peaks = peaks - delta
        if (not self.hasbaseline) and self.pivot is Pivot.bottom:
            # pivot.bottom implies that we consider the first experimental
            # peak to be the baseline. Since we don't use it in the fit, we
            # remove it
            peaks = peaks[1:]

        if self.pivot is Pivot.top:
            hpdelta = self.peaks[-1]
            hpin    = self.peaks - hpdelta
        else:
            hpdelta = 0
            hpin    = self.peaks

        return delta, peaks.astype('f4'), hpdelta, hpin.astype('f4')

class GaussianProductFit(HairpinFitter, GriddedOptimization):
    """
    Matching experimental peaks to hairpins using a cost function:

    If:

        R(X, Y) = Σ_{i, j} exp(-((x_i -y_j)/σ)²)


    Then the cost is:

        1 - R(X, Y)/sqrt(R(X, X) R(Y, Y))
    """
    precision:float = 15.
    @initdefaults(frozenset(locals()))
    def __init__(self, **kwa):
        HairpinFitter.__init__(self, **kwa)
        GriddedOptimization.__init__(self, **kwa)

    def iterate(self, peaks:np.ndarray) -> Iterator[Distance]:
        "computes stretch and bias for potential pairings"
        yield self.optimize(peaks)

    def optimize(self, peaks: np.ndarray) -> Distance:
        "optimizes the cost function"
        best = self._defaultdistance()
        if len(self.peaks) == 0:
            return best

        delta, peaks, hpdelta, hpin = self._applypivot(peaks)
        if len(peaks) > 1:
            args  = self.optimconfig(symmetry     = self.symmetry is Symmetry.both,
                                     noise        = self.precision,
                                     singlestrand = 1. if self.hassinglestrand else 0.,
                                     baseline     = 1. if self.hasbaseline     else 0.)

            bias  = 0. if self.bias.center is None else delta
            for vals in self.grid:
                args.update(min_stretch = vals[0] - self.stretch.step,
                            stretch     = vals[0],
                            max_stretch = vals[0] + self.stretch.step,
                            min_bias    = -vals[0]*(vals[1]+bias) - vals[0]*self.bias.step,
                            bias        = -vals[0]*(vals[1]+bias),
                            max_bias    = -vals[0]*(vals[1]+bias) + vals[0]*self.bias.step)

                try:
                    out = self._optimize(hpin, peaks, args)
                except Exception: # pylint: disable=broad-except
                    continue
                else:
                    if out[0] < best[0]:
                        best = out
        return Distance(best[0], best[1], delta-(best[2]+hpdelta)/best[1])

    def value(self, peaks: np.ndarray, stretch, bias) -> Tuple[float, float, float]:
        "computes the cost value at a given stretch and bias as well as derivatives"
        peaks, hpin = self._applypivot(peaks)[1::2]
        if len(peaks) == 0:
            return 0., 0., 0.
        if any(isinstance(i, (Sequence, np.ndarray)) for i in (stretch, bias)):
            stretch = np.asarray(stretch)
            bias    = -np.asarray(bias)*stretch
            fcn     = lambda i, j: self._value(hpin, peaks, i, j,
                                               symmetry = self.symmetry is Symmetry.both,
                                               noise    = self.precision)
            ufcn    = np.frompyfunc(fcn, 2, 3)
            return ufcn(stretch, bias)
        return self._value(hpin, peaks, stretch, -bias*stretch,
                           symmetry     = self.symmetry is Symmetry.both,
                           noise        = self.precision,
                           singlestrand = self.hassinglestrand)

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
    symmetry = Symmetry.both
    window   = 10.
    def _chisquare(self, hpin, peaks, stretch, bias):
        sym = Symmetry.both if self.symmetry is Symmetry.both else Symmetry.left
        return ChiSquare(hpin, peaks, self.window, stretch, bias, sym)

    def _optimalvalue(self, hpin: np.ndarray, peaks: np.ndarray, # type: ignore
                      stretch:float, bias:float, **_):
        return self._chisquare(hpin, peaks, stretch, bias).optimize(*self.constraints())

    def _value(self, hpin: np.ndarray, peaks: np.ndarray, # type: ignore
               stretch:float, bias:float, **_):
        return self._chisquare(hpin, peaks, stretch, bias).value()

    def _optimize(self, hpin, peaks, args):
        "optimizes the cost function"
        pars = _cost.optimize(hpin, peaks, **args)
        return self._optimalvalue(hpin, peaks, pars[1], pars[2])

    def optimize(self, peaks: np.ndarray) -> Distance:
        "optimizes the cost function"
        peaks = np.asarray(peaks)
        ret   = super().optimize(peaks)
        if self.symmetry is Symmetry.right and len(peaks) > 1:
            chi = ChiSquare(self.peaks, peaks, self.window, ret[1], ret[2],
                            self.symmetry, self.hassinglestrand, True)
            return Distance(chi.value()[0], ret[1], ret[2])
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
    symmetry  = Symmetry.both
    bounds    = 10.
    @initdefaults(frozenset(locals()))
    def __init__(self, **kwa):
        super().__init__(**kwa)

    def iterate(self, peaks:np.ndarray) -> Iterator[Distance]:
        "computes stretch and bias for potential pairings"
        if len(self.peaks) == 0:
            return

        delta, peaks, hpdelta, hpin = self._applypivot(peaks)
        if len(peaks) < 2:
            return

        rng   = lambda val: ((val.center if val.center else 0.) - val.size,
                             (val.center if val.center else 0.) + val.size)
        args  = rng(self.stretch)+rng(self.bias)
        centr = sum(args[:2])*.5, sum(args[2:])*.5

        if self.bounds > 0.:
            itr = tuple(_match.BoundedPeakIterator(hpin, peaks, self.bounds, *args))
        else:
            itr = tuple(_match.PeakIterator(hpin, peaks, *args))
        itr  += (centr,)

        chi   = ChiSquare(hpin, peaks, self.window,
                          symmetry     = self.symmetry,
                          singlestrand = self.hassinglestrand)
        cstr  = self.constraints()
        fcn   = lambda x: Distance(x[0], x[1], delta-(x[2]+hpdelta)/x[1])
        yield from (fcn(chi.update(i[0], i[1], True).optimize(*cstr)) for i in itr)

    def optimize(self, peaks:np.ndarray) -> Distance:
        "computes stretch and bias for potential pairings"
        return min(self.iterate(peaks), default = self.defaultdistance(peaks))

    def value(self, peaks:np.ndarray,
              stretch: Union[float, np.ndarray],
              bias:    Union[float, np.ndarray]) -> float:
        "computes the cost value at a given stretch and bias"
        peaks = np.asarray(peaks, dtype = 'f4')
        if any(isinstance(i, (np.ndarray, Sequence)) for i in  (stretch, bias)):
            fcn = np.frompyfunc(partial(self._cost_function, self.peaks, peaks), 2, 1)
            return fcn(stretch, bias)
        return self._cost_function(self.peaks, peaks, stretch, bias)

    def defaultdistance(self, peaks:np.ndarray) -> Distance:
        "computes stretch and bias for potential pairings"
        dflt = self._defaultdistance()
        val  = self._cost_function(self.peaks, peaks, dflt[1], dflt[2])
        return Distance(val, dflt[1], dflt[2])

    def _cost_function(self, left, right, stretch: float, bias: float):
        return ChiSquare(left, right, self.window, stretch, bias,
                         self.symmetry, self.hassinglestrand, True).value()[0]

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

    def __delayed_init__(self, _):
        self.peaks = [np.asarray(i, dtype = "f4") for i in self.peaks]
        if len(self.peaks) > 2:
            raise NotImplementedError()

        for i in ('stretch', 'bias'):
            val = getattr(self, i)
            if not isinstance(val, Range):
                setattr(self, i, Range(**val) if isinstance(val, dict) else Range(*val))

    def optimize(self, peaks:np.ndarray) -> Distance:
        "computes stretch and bias for potential pairings"
        peaks = np.asarray(peaks, dtype = 'f4')
        if self.pivot in (Pivot.top, Pivot.bottom):
            delta     = peaks[-1          if self.pivot is Pivot.top else 0]
            hpdelta   = self.peaks[1][-1] if self.pivot is Pivot.top else self.peaks[0][0]

            cpy       = copy(self)
            cpy.peaks = [i - hpdelta for i in self.peaks]
            out       = getattr(cpy, '_optimize')(peaks-delta)
            return Distance(out[0], out[1], out[2]+(delta-hpdelta/out[1]))
        return self._optimize(peaks)

    def value(self, peaks:np.ndarray,
              stretch: Union[float, np.ndarray],
              bias:    Union[float, np.ndarray]) -> float:
        "computes the cost value at a given stretch and bias"
        raise NotImplementedError()

    def _optimize(self, peaks:np.ndarray) -> Distance:
        "computes stretch and bias for potential pairings"
        rng  = lambda val: ((val.center if val.center else 0.) - val.size,
                            (val.center if val.center else 0.) + val.size)
        bias, stretch = rng(self.bias), rng(self.stretch)

        extr = [(i[-1]-i[0])/stretch[0]+bias[1] for i in self.peaks]
        pks  = [np.asarray(peaks[:np.searchsorted(peaks, peaks[0]+extr[0])], dtype = 'f4'),
                np.asarray(peaks[np.searchsorted(peaks,  peaks[-1]-extr[1]):], dtype = 'f4')
               ]
        if any(len(i) < 2 for i in pks):
            return self._defaultdistance()

        args = stretch + (-np.finfo('f4').max, np.finfo('f4').max) + (True,)
        itrs = [tuple(np.copy(i) for i in _match.PeakIterator(ref, item, *args))
                for ref, item in zip(self.peaks, pks)]

        nref = sum(len(i) for i in self.peaks)
        minv = min((self.__chisquare(nref, pks, inds) for inds in product(*itrs)),
                   default = self._defaultdistance())
        return Distance(minv[0], minv[1], -(np.asarray(minv[2])/minv[1]))

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
            return self._defaultdistance()
        stretch, biases = self.__params(peaks, indexes)

        inds = [_match.compute(i, j*stretch+bias, self.window)
                for i, j, bias in zip(self.peaks, peaks, biases)]
        if any(len(i) == 0 for i in inds):
            return self._defaultdistance()
        stretch, biases = self.__params(peaks, inds)

        inds = [_match.compute(i, j*stretch+bias, self.window)
                for i, j, bias in zip(self.peaks, peaks, biases)]
        chi2 = sum(((i-stretch*j-bias)**2).sum()
                   for i, j, bias in zip(*self.__selection(peaks, inds),
                                         biases))/self.window**2

        chi2 += (npeaksexpected-sum(len(i) for i in inds))**2
        return np.sqrt(max(0., chi2)/npeaksexpected), stretch, biases

class PiecesPeakGridFit:
    "fit by pieces"
    defaultstretch: float      = OptimizationParams.defaultstretch
    pieces : List[PeakGridFit] = []
    window : float             = 10.
    stretch: Range             = Range(None, 10., 10.)
    bias:    Range             = Range(None, 3, 3)
    ordered: bool              = True

    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        pass

    def appendpiece(self, **kwa):
        "adds a fit to the list"
        self.pieces.append(PeakGridFit(**kwa))

    def optimize(self, peaks:np.ndarray) -> List[Distance]:
        "computes stretch and bias for potential pairings"
        itr: Iterator[List[Distance]] = self.iterate(peaks)
        dflt: List[Distance]          = [i.defaultdistance(peaks) for i in self.pieces]
        return min(itr, default = dflt, key = lambda x: sum(j[0] for j in x))

    def iterate(self, peaks, **kwa) -> Iterator[List[Distance]]:
        "iterate over stretch & bias options"
        cur = copy(self)
        if self.ordered and len(self.pieces) > 2:
            raise NotImplementedError()

        for i, j in enumerate(self.pieces):
            if len(kwa):
                j = copy(j)
                for _ in kwa.items():
                    setattr(j, *_)

            if len(self.pieces) == 1:
                yield from ([dist] for dist in j.iterate(peaks))
                continue

            cur.pieces = self.pieces[:i]+self.pieces[i+1:]
            for dist in j.iterate(peaks):
                ids = matchpeaks(j.peaks, (peaks-dist[2])*dist[1], self.window) >= 0
                if not np.any(ids):
                    continue
                rem = (
                    peaks[~ids]                      if not self.ordered else
                    peaks[np.nonzero(ids)[0][-1]+1:] if i == 0           else
                    peaks[:np.nonzero(ids)[0][0]]
                )
                if len(rem) < 2:
                    continue

                cstrs = dict(
                    stretch = Range(dist[1], self.stretch[1], self.stretch[2]),
                    bias    = Range(dist[2], self.bias[1],    self.bias[2])
                )
                t2e  = j.peaks[-1 if i == 0 else 0]/dist[1]+dist[2]
                for dist2 in cur.iterate(rem, **cstrs):
                    if self.ordered:
                        t2e2  = cur.pieces[0].peaks[0 if i == 0 else -1]/dist2[0][1]+dist2[0][2]
                        if (i == 0 and t2e >= t2e2) or (i == 1 and t2e2 >= t2e):
                            continue
                    yield dist2[:i]+[dist]+dist2[i:]

    def reconstruct(self, distances: Sequence[Distance]):
        "return the list of theoretical peaks on a single axis"
        return [
            self.pieces[0].peaks,
            *(
                ((i.peaks/j[1]+j[2])-distances[0][2])*distances[0][1]
                for i, j in zip(self.pieces[1:], distances[1:])
            )
        ]

def matchpeaks(ref, peaks, window):
    """"
    return a list of indexes of matched peaks in ref

    ```python
    out = matchpeaks([1,2,3,4,5], [2,4, 5, 10], .5)
    assert tuple(out) == (1, 3, 4, np.iinfo('i4').max)

    out = matchpeaks([2,5], [2,4, 5, 10], .5)
    assert tuple(out) == (0, np.iinfo('i4').max, 1, np.iinfo('i4').max)
    ```
    """
    ref   = np.asarray(ref,   dtype = 'f4')
    peaks = np.asarray(peaks, dtype = 'f4')
    ids   = _match.compute(ref, peaks, window)
    arr   = np.full(len(peaks), np.iinfo('i4').min, dtype = 'i4')
    arr[ids[:,1]] = ids[:,0]
    return arr

PEAKS_DTYPE = np.dtype([('zvalue', 'f4'), ('key', 'i4')])  # pylint: disable=invalid-name
PEAKS_TYPE  = Union[Sequence[Tuple[float,int]],np.ndarray] # pylint: disable=invalid-name
class PeakMatching(HairpinFitter, PointwiseOptimization):
    "Identifying experimental peaks with the theoretical ones"
    window          = 10.
    bases           = (20, 20)
    dataprecisions  = 1., 1e-3
    @initdefaults(frozenset(locals()))
    def __init__(self, **kwa):
        HairpinFitter.__init__(self, **kwa)
        PointwiseOptimization.__init__(self, **kwa)

    @staticmethod
    def empty(peaks) -> PEAKS_TYPE:
        "return an empty output"
        ided           = np.empty((len(peaks),), dtype = PEAKS_DTYPE)
        ided['zvalue'] = peaks
        ided['key']    = np.iinfo('i4').min
        return ided

    def pair(self, peaks:np.ndarray, stretch = 1., bias = 0.) -> PEAKS_TYPE:
        "returns experimental peaks paired to the theory"
        hpin = self.peaks
        ided = self.empty(peaks)

        if len(peaks) > 0 and len(hpin) > 0:
            peaks = stretch*(peaks-bias)
            ids   = _match.compute(hpin, peaks, self.window)
            ided['key'][ids[:,1]] = np.int32(hpin[ids[:,0]]) # type: ignore
        return ided

    def nfound(self, peaks:np.ndarray, stretch = 1., bias = 0.) -> int:
        "returns the number of paired peaks"
        hpin = self.peaks
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

        hpin = self.peaks
        return _match.distance(hpin, peaks, self.window, stretch, -bias*stretch)

    def optimize(self, peaks:np.ndarray) -> Distance:
        "Optimizes the distance"
        best  = self._defaultdistance()
        if len(peaks) > 1:
            rng   = lambda x, y, z: (('min_'+x, y-z), (x, y), ('max_'+x, y+z))
            args  = self.optimconfig(window = self.window)
            hpin  = self.peaks
            pots  = {i: self.distance(peaks, *i)[-1]
                     for i in self.pointgrid(self.peaks, peaks)}
            maxi  = max(pots.values(), default = best[0])-1 # type: ignore
            good  = set((int(i[0]/self.dataprecisions[0]), int(i[1]/self.dataprecisions[1]))
                        for i, j in pots.items() if j >= maxi)
            for ivals in good:
                vals = ivals[0]*self.dataprecisions[0], ivals[1]*self.dataprecisions[1]
                args.update(rng('stretch',  vals[0],         self.stretch.step))
                args.update(rng('bias',    -vals[0]*vals[1], self.bias.step*vals[0]))
                try:
                    out = _match.optimize(hpin, peaks, **args)
                except Exception: # pylint: disable=broad-except
                    continue
                else:
                    if out[0] < best[0]:
                        best = out

        return Distance(best[0], best[1], -best[2]/best[1])
