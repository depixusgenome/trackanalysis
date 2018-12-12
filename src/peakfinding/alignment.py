#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Cycle alignment: define an absolute zero common to all cycles"
from   typing                  import (Union, Optional, Iterable, List, Tuple,
                                       Sized, cast)

import numpy                   as     np
from   numpy.lib.stride_tricks import as_strided
from   numpy.linalg            import lstsq, norm as lnorm
from   scipy.optimize          import minimize_scalar, fmin_cobyla

from   utils                   import initdefaults, updatecopy, kwargsdefaults
from   .histogram              import Histogram
from   .groupby                import SubPixelPeakPosition

class PeakCorrelationAlignmentAction:
    """
    Container class for computing a bias with given options.

    Attributes:

    * *factor*: multiplicative factor on the overall precision.
    * *zcost*: amount per unit of translation by which the cost function
    must outperform for that translation to be selected.
    * *maxmove*: max amount by which a cycle may be translated.
    * *minevents*: min number of events in a cycle required for a bias to
    be computed.
    """
    factor                      = 1.5
    zcost     : Optional[float] = 0.05
    minevents : Optional[float] = 2
    maxmove                     = int(5//factor)
    subpixel                    = False
    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        pass

    def costarray(self, wtab, projector) -> Union[int,np.ndarray]:
        "computes a z-cost array"
        if not self.zcost:
            return (lambda x: (x,),)

        osamp = projector.exactoversampling
        if wtab.cost[1:] == (self.maxmove, self.zcost, osamp):
            return wtab.cost

        arr   = np.arange(1,  self.maxmove*osamp)
        cost  = self.zcost/osamp
        arr   = 1. - cost*np.concatenate([arr[::-1], [0, 0], arr])

        return lambda x: x*arr, self.maxmove, self.zcost, osamp

    def projector(self, wtab):
        "projects the data"
        edge = (self.maxmove + wtab.parent.projector.kernel.width)*2
        return updatecopy(wtab.parent.projector,
                          zmeasure  = None,
                          edge      = edge,
                          precision = wtab.precision*self.factor)

    def reference(self, _, projector, hists):
        "computes a reference"
        maxt = projector.exactoversampling*self.maxmove*2
        return np.mean([i[maxt//2] for i in hists[0]], 0)

    @staticmethod
    def center(bias):
        "centers the bias"
        bias -= np.median(bias)
        return bias

    def good(self, wtab):
        "finds cycles to align"
        good = np.array([len(i) for i in wtab.data]) >= self.minevents
        if not np.any(good):
            return None
        return good

    def argmax(self, wtab):
        "computes the argmax function"
        cost     = wtab.cost[0]
        subpixel = wtab.parent.subpixel
        if self.subpixel and callable(subpixel):
            def _argmax(ref, cur):
                arr  = cost(np.dot(cur, ref))
                ind  = np.argmax(arr)
                subp = subpixel(arr, ind)
                return ind if subp is None else subp
            return _argmax

        return lambda ref, cur: np.argmax(cost(np.dot(cur, ref)))

    def hists(self, wtab, projector, bias, good):
        "creates the histograms"
        bias  = bias if bias is None else bias[good]
        hists = projector(wtab.data[good], bias = bias, separate = True)

        maxt   = projector.exactoversampling*self.maxmove*2
        matrix = tuple(as_strided(cur,
                                  shape   = (maxt, len(cur)-maxt),
                                  strides = (cur.strides[0],)*2)
                       for cur in hists[0])
        return (matrix,)+hists[1:]

    def bias(self, wtab, projector, bias):
        "finds the bias"
        good = self.good(wtab)
        if good is None:
            return bias

        hists = self.hists(wtab, projector, bias, good)
        ref   = self.reference(wtab, projector, hists)

        argmax = self.argmax(wtab)
        found  = np.array([argmax(ref, i) for i in hists[0]])

        if bias is None:
            bias = np.zeros((len(wtab.data),), dtype = 'f4')

        maxt        = projector.exactoversampling*self.maxmove*2
        bias[good] -= (found - maxt//2)*hists[2]
        return self.center(bias)

    def __call__(self, wtab, bias):
        projector = self.projector(wtab)
        wtab.cost = self.costarray(wtab, projector)
        return self.bias(wtab, projector, bias)

class PeakCorrelationAlignmentWorkTable:
    "Contains data to be saved from action to action"
    def __init__(self, parent, precision, data, **_):
        self.parent    = parent
        self.precision = precision
        self.data      = data
        self.cost      = (1,)

class PeakCorrelationAlignment:
    """
    Finds biases which correlate best a cycle's histogram to the histogram of
    all cycles. This repeated multiple times with the latter histogram taking
    prior biases into account.

    Biases are furthermore centered at zero around their median.

    # Attributes

    * *actions*:   a list of aligment actions with their options
    * *subpixel*:  algorithm for subpixel precision on the correlation peaks
    * *projector*: how to project cycles unto an axis
    """

    Action    = PeakCorrelationAlignmentAction
    actions   = [Action(),
                 Action(),
                 Action(factor = 1, maxmove   = 3),
                 Action(factor = 1, minevents = 1, maxmove = 2, subpixel = True)]
    projector = Histogram()
    subpixel  = SubPixelPeakPosition()

    __KEYS    = frozenset(locals())
    @initdefaults(__KEYS,
                  projector = 'update',
                  zcost     = lambda self, j: self.setzcost(j),
                  maxmove   = lambda self, j: self.setmaxmove(j),
                  factor    = lambda self, j: self.setfactor(j))
    def __init__(self, **_):
        pass

    def __set(self, attr, vals):
        "sets the attribute for all actions"
        if isinstance(vals, (list, tuple)):
            for action, val in zip(self.actions, vals):
                setattr(action, attr, val)
        else:
            for action in self.actions:
                setattr(action, attr, vals)

    def setzcost(self, cost):
        "sets the z-cost for all actions"
        self.__set('zcost', cost)

    def setmaxmove(self, mmove):
        "sets max move for all actions"
        self.__set('maxmove', mmove)

    def setfactor(self, factor):
        "sets max move for all actions"
        self.__set('factor', factor)

    @kwargsdefaults(__KEYS)
    def __call__(self,
                 data:      Union[np.ndarray, Iterable[np.ndarray]],
                 precision: float = None, **kwa) -> np.ndarray:
        data, prec = self.projector.positionsandprecision(data, precision)
        wtab       = PeakCorrelationAlignmentWorkTable(self, prec, data, **kwa)
        bias       = None
        for action in self.actions:
            bias = action(wtab, bias)
        return np.zeros(len(data), dtype = 'f4') if bias is None else bias

    @classmethod
    def run(cls, data: Iterable[np.ndarray], **kwa):
        "runs the algorithm"
        return cls(**kwa)(data)

class SymetricExpectedPositionAlignment:
    """
    For each cycle, we find the best position such that expected position
    probabilities are symetric.

    Expected probabilities are for a given event and its neighbour the gaussian
    from that neighbour to the expected position of the event.

    The expected position of an event is the average of neighbouring events weighted
    by a gaussian from those neighbours to the event.

    In otherwords, we minimize ||B - B'||², where B is a NxN matrix with N the
    number of events and:

        B_ij           = Gauss(x_ij, x_ii, e_i)

    where:

        e_i            = ∑_j x_ij Gauss(x_ij, x_ii, x_ii)
        Gauss(α, β, γ) = exp(-( (α-β) δ(||α - γ|| < ξ σ) /σ )²/2)

    This minimization is performed along every axis (ie event) independently
    once per estimation.

    Setting `averageout` to a value between 0 and 1, it's possible to average
    bias values at every estimation using the following formula:


        bias_i        = (1-averageout) bias_i + averageout averagebias_i
        averagebias_i = ∑_j bias_j Gauss(x_ij, x_ii, x_ii)
    """
    eventwindow                   = 4
    searchwindow                  = 2.5
    estimations                   = 1
    discardrange: Optional[float] = None
    averageout                    = .5
    @initdefaults
    def __init__(self, **kwa):
        pass

    def biascost(self, delta, precision, cur, vals) -> float:
        "best bias for a given cycle"
        cost  = 0.
        rng   = self.eventwindow*precision
        cur   = cur+delta
        for i, j, point in zip(np.searchsorted(vals, cur-rng),
                               np.searchsorted(vals, cur+rng, 'right'),
                               cur):
            if i == j:
                continue

            curpos = self.__avg(vals[i:j], point, point, precision)
            minpos = np.searchsorted(vals, vals[i:j]-rng)
            maxpos = np.searchsorted(vals, vals[i:j]+rng, 'right')
            pts    = np.array([self.__avg(vals[i1:i2], val, point, precision)
                               for i1, i2, val in zip(minpos, maxpos, vals[i:j])],
                              dtype = 'f4')

            cost  += lnorm(self.__norm(curpos-pts, precision)
                           -self.__norm(curpos-vals[i:j], precision))**2/(j-i+1)

        return cost

    def computebias(self,
                    events:   np.ndarray,
                    icyc:     np.ndarray,
                    previous: np.ndarray,
                    precision: float) -> np.ndarray:
        "computes all best biases"
        vals, cycs  = self.__data(events, icyc, previous)
        bnds        = (-self.searchwindow*precision, self.searchwindow*precision)

        previous[:] = [minimize_scalar(self.biascost,
                                       args   = (precision, cur, vals[cycs != i]),
                                       bounds = bnds, method = 'bounded').x
                       for i, cur in enumerate(events)]

        self.__averageout(vals, cycs, previous, precision)
        previous   -= np.median(previous)
        return previous

    def __call__(self,
                 data:      Union[np.ndarray, Iterable[np.ndarray]],
                 precision: float     = None,
                 projector: Histogram = None)-> np.ndarray:
        if projector is not None:
            data, prec = projector.positionsandprecision(data, precision)
        elif precision is None:
            raise ValueError()
        else:
            tmp        = np.empty(len(cast(Sized, data)), dtype = 'O')
            tmp[:]     = [np.asarray(i, dtype = 'f4') for i in data]
            data, prec = tmp, cast(float, precision)
        allb  = np.zeros(len(data), dtype = 'f4')

        ievts = np.array([len(i) > 0 for i in data], dtype = 'bool')
        data  = data[ievts]
        icycs = np.concatenate([np.full(len(j), i, dtype = 'i4')
                                for i, j in enumerate(data)])
        bias  = np.zeros(len(data), dtype = 'f4')
        for _ in range(self.estimations):
            self.computebias(data, icycs, bias, prec)

        if self.discardrange is not None:
            cpy         = self.computebias(data, icycs, np.copy(bias), prec)
            good        = np.abs(cpy-bias) < self.discardrange*prec
            bias[~good] = np.NaN
            bias[good] -= np.median(bias[good])

        allb[ievts] = bias
        return allb

    @classmethod
    def run(cls,
            data:      Iterable[np.ndarray],
            precision: float     = None,
            projector: Histogram = None,
            **kwa)-> np.ndarray:
        "runs the algorithm"
        return cls(**kwa)(data, precision, projector)

    @staticmethod
    def __data(events, icyc, previous) -> Tuple[np.ndarray, np.ndarray]:
        vals = np.concatenate(events)+previous[icyc]
        inds = np.argsort(vals)
        return vals[inds], icyc[inds]

    def __averageout(self, vals, cycs, previous, precision):
        if self.averageout <= 0.:
            return

        rng = self.eventwindow*precision
        tmp = np.copy(previous)
        for i in range(cycs.max()):
            cur    = vals[cycs == i]
            minpos = np.searchsorted(vals, cur-rng)
            maxpos = np.searchsorted(vals, cur+rng, 'right')
            avg    = np.mean([np.average(tmp[cycs[i1:i2]],
                                         weights = self.__norm(vals[i1:i2]-point, precision))
                              for i1, i2, point in zip(minpos, maxpos, cur)])
            previous[i] = previous[i]*(1.-self.averageout) + self.averageout*avg

    @classmethod
    def __avg(cls, pos, center, point, prec):
        wpts = cls.__norm(np.copy(pos), prec)
        wcur = np.exp(-.5*((center-point)/prec)**2)
        return (np.inner(wpts, pos)+point*wcur)/(wcur+wpts.sum())

    @staticmethod
    def __norm(pos, prec):
        pos /= prec
        pos *= pos
        pos *= -.5
        return np.exp(pos)

class SymetricExpectedPositionCOBYLAAlignment:
    """
    For each cycle, we find the best position such that expected position
    probabilities are symetric and that expected position are clustered together

    Expected probabilities are for a given event and its neighbour the gaussian
    from that neighbour to the expected position of the event.

    The expected position of an event is the average of neighbouring events weighted
    by a gaussian from those neighbours to the event.

    In otherwords, we minimize ||B - B'||² - ||C||², where B and C are a NxN
    matrix with N the number of events and:

        B_ij           = Gauss(x_ij, x_ii, e_i)
        C_ij           = Gauss(e_i, e_j, e_i)

    where:

        e_i            = ∑_j x_ij Gauss(x_ij, x_ii, x_ii)
        Gauss(α, β, γ) = exp(-( (α-β) δ(||α - γ|| < ξ σ) /σ )²/2)

    This minimization is performed along all axes (ie events) at a time using a
    COBYLA minimizer
    """
    eventwindow     = 4
    searchwindow    = 2.5
    weights         = 1., 1.
    constraintrange = 3.
    rhobegin        = 1/3
    rhoend          = 1/20
    @initdefaults
    def __init__(self, **kwa):
        pass

    @classmethod
    def run(cls,
            data:      Iterable[np.ndarray],
            precision: float     = None,
            projector: Histogram = None,
            **kwa)-> np.ndarray:
        "runs the algorithm"
        return cls(**kwa)(data, precision, projector)

    def __call__(self,
                 data:      Union[np.ndarray, Iterable[np.ndarray]],
                 precision: float     = None,
                 projector: Histogram = None)-> np.ndarray:
        """
        Estimation of all cycle deltas at a time.

        This takes a minute to run.
        """
        if projector is not None:
            data, prec = projector.positionsandprecision(data, precision)
        elif precision is None:
            raise ValueError()
        else:
            tmp        = np.empty(len(cast(Sized, data)), dtype = 'O')
            tmp[:]     = [np.asarray(i, dtype = 'f4') for i in data]
            data, prec = tmp, cast(float, precision)

        return fmin_cobyla(lambda x: self.biascost(x, data, prec),
                           x0     = np.zeros(len(data), 'f8'),
                           cons   = lambda x: self.biasconstraint(x, prec),
                           rhobeg = prec*self.rhobegin, rhoend = prec*self.rhoend)

    def biasconstraint(self, biases: np.ndarray, precision: float) -> float:
        "best bias for a given cycle"
        return np.sum(precision*self.constraintrange-np.abs(biases))

    # pylint: disable=too-many-locals
    def biascost(self, bias: np.ndarray, events: np.ndarray, precision: float) -> float:
        "bias cost"
        evts      = np.sort(np.concatenate([i+j for i, j in zip(events, bias)]))
        minpos    = np.searchsorted(evts, evts-self.eventwindow*precision)
        maxpos    = np.searchsorted(evts, evts+self.eventwindow*precision, 'right')
        epos      = np.array([self.__avg(evts[ix1:ix2], pos, precision)
                              for ix1, ix2, pos in zip(minpos, maxpos, evts)],
                             dtype = 'f4')
        expect    = np.empty(len(evts), dtype = 'O')
        expect[:] = [self.__wgt(evts[ix1:ix2], pos, precision)
                     for ix1, ix2, pos in zip(minpos, maxpos, epos)]

        cost      = 0.
        if self.weights[0]:
            for ipos, ix1, ix2 in zip(range(len(evts)), minpos, maxpos):
                tmp   = [i[j] for i, j in zip(expect[ix1:ix2], ipos-minpos[ix1:ix2])]
                cost += lnorm(expect[ipos] - tmp)**2

        if self.weights[1]:
            pkcount  = sum(lnorm(self.__wgt(epos[ix1:ix2], pos, precision))**2
                           for ix1, ix2, pos in zip(minpos, maxpos, epos))
            cost    -= self.weights[1] * pkcount
        return cost

    @staticmethod
    def __wgt(left: np.ndarray, right:float, precision: float):
        return np.exp(-.5*((left-right)/precision)**2)

    @classmethod
    def __avg(cls, left: np.ndarray, right:float, precision: float):
        return np.average(left, weights = cls.__wgt(left, right, precision))

class PeakExpectedPositionAlignment(SymetricExpectedPositionAlignment):
    "Aligns cycles using a maximum likelihood position on events in the cycle"
    estimations = 2
    rigidity    = .1
    averageout  = 0.
    @initdefaults
    def __init__(self, **kwa):
        super().__init__(**kwa)

    def biascost(self, delta, precision, cur, vals) -> float:
        "best bias for a given cycle"
        cost  = 0.
        wevts = 0
        cnt   = 0
        rng   = self.eventwindow*precision
        cur   = cur+delta
        for i, j, point in zip(np.searchsorted(vals, cur-rng),
                               np.searchsorted(vals, cur+rng, 'right'),
                               cur):
            if i == j:
                cost += rng**2
            else:
                arr    = vals[i:j]
                wgt    = np.exp(-.5*((arr-point)/precision)**2)
                cost  += ((point+np.inner(arr, wgt))/(wgt.sum()+1.)-point)**2
                wevts += np.log(j-i+1)
            cnt  += 1
        return cost/cnt + self.rigidity/(wevts+0.001)*delta**2

class PeakPostAlignment:
    """
    contains means for getting event stats
    """
    norm  = 'ones_like' # could be sqrt
    @initdefaults({"norm"})
    def __init__(self, **kwa):
        pass

    DTYPE = np.dtype([('weight', 'f4'), ('mean', 'f4')])
    def tostats(self, peaks) -> np.ndarray:
        "changes a list of peaks to stats"
        stats = np.array([[self.__compute(i) for i in j] for j in peaks['events']],
                         dtype = self.DTYPE)
        if self.norm:
            stats['weight'][:] = (self.norm if callable(self.norm) else
                                  getattr(np, self.norm)
                                 )(stats['weight'])

        nans = np.isnan(stats['mean'])
        stats['weight'][nans] = 0.
        stats['mean'][nans]   = 0.
        return stats

    @staticmethod
    def __compute(vals):
        if vals.dtype != 'O':
            vals = vals['data']
        cnt = len(vals)
        return ((0,                         np.NaN)                     if cnt == 0 else
                (vals[0].size,              np.nanmean(vals[0]))        if cnt == 1 else
                (sum(_.size for _ in vals), np.nanmean(np.concatenate(vals))))

    def correctevents(self, evts):
        "corrects the biases on current peaks"
        stats  = self.tostats(evts)
        biases = self(stats)
        evts['peaks'] = np.average(stats['mean']+biases, 1, stats['weight'])
        for i in evts['events']:
            for j, k in zip(i, biases):
                j['data'][:] += k
        return evts

    def __call__(self, stats):
        raise NotImplementedError()

class MinBiasPeakAlignmentAction:
    """
    Container class for computing a bias with given options.

    Attributes:

    * *minevents*: min number of events in a cycle required for a bias to
    be computed.
    """
    minevents                             = 1
    repeats                               = 10
    peakmask: Union[List[int], int, None] = 1
    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        pass

class MinBiasPeakAlignment(PeakPostAlignment):
    """
    Provided with a list of peaks and their events, aligns them by removing the bias
    per cycle.
    """
    iterations = [MinBiasPeakAlignmentAction()]
    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        super().__init__(**_)

    def __call__(self, stats: np.ndarray):
        if len(stats) == 0:
            return np.zeros(0, dtype = 'f4')

        delta = np.zeros(len(stats[0]), dtype = 'f4')
        if len(stats) == 1:
            return delta

        for itr in self.iterations:
            if isinstance(itr.peakmask, int) and itr.peakmask < 0:
                weights  = stats['weight'][:itr.peakmask]
                means    = stats['mean'][:itr.peakmask]
            elif isinstance(itr.peakmask, int) and itr.peakmask > 0:
                weights  = stats['weight'][itr.peakmask:]
                means    = stats['mean'][itr.peakmask:]
            elif itr.peakmask not in (None, 0):
                weights  = stats['weight'][itr.peakmask]
                means    = stats['mean'][itr.peakmask]
            else:
                weights  = stats['weight']
                means    = stats['mean']

            cyccount = np.sum(weights > 0.0, 0)
            for _ in range(itr.repeats):
                goodcyc = np.where(cyccount >= itr.minevents)[0]
                if len(goodcyc) < 2:
                    continue

                tmp             = means+delta
                peaks           = np.average(tmp, 1, weights)[:,None]
                delta[goodcyc] += np.average(peaks-tmp[:, goodcyc], 0, weights[:, goodcyc])
                delta          -= np.median(delta)
        return delta

class GELSPeakAlignment(PeakPostAlignment):
    """
    Provided with a list of peaks and their events, aligns them by removing the bias
    per cycle.

    The following equation is minimized:

        ∑_i  ∑_j ((1/n_i ∑_k(x_ik + δ(x_ik))) - x_ij - δ(x_ij))²
        + α x (distortion constraints)

    where the first summation (i) is over peaks and the next ones (j and k) are
    over items in the peaks. The summation over peaks is for finding the best biases.

    Two other constraints are added in order to limit the distortion of the
    z-axis:

    1. Consider that cycles might be disconnected in that a first set has
    bindings only ever for one set of peaks and another set cycles for another
    *disconnected* set of peaks. In order to limit this, we add a constraint
    that forces all cycles to keep the same average distance between
    themselves.
    2. The last constraint is that the average of all bindings should remain the same.
    """
    alpha = 1.
    beta  = 1.
    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        super().__init__(**_)

    def matrixes(self, peaks:np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        "Returns a matrix which can be used to minimize the distances"
        good  = peaks['weight'] > 0.
        npks  = good.sum()

        cycs  = self.__computecycles(good)
        arr   = np.zeros((npks+len(cycs), peaks.shape[1]), 'f8')
        vect  = np.zeros(arr.shape[0], 'f8')
        ind   = self.__addpeakconstraints(peaks, good, arr, vect)
        self.__addcycleconstraints(peaks, good, cycs, arr[ind:,:], vect[ind:])
        self.__addavgconstraint(good, arr[-1:,:])
        return arr, vect

    def __call__(self, peaks: np.ndarray) -> np.ndarray:
        if len(peaks) == 0:
            return np.zeros((0,), 'f4')

        peaks        = peaks[np.sum(peaks['weight'] > 0, axis = 1) > 0, :]
        good         = np.sum(peaks['weight'] > 0, axis = 0) > 0
        out          = lstsq(*self.matrixes(peaks[:, good]), None)[0]
        biases       = np.zeros(peaks.shape[1], 'f4')
        biases[good] = out - np.mean(out)
        return biases

    @staticmethod
    def __addpeakconstraints(peaks, good, arr, vect):
        ind  = 0
        for vals, corr in zip(peaks, good):
            assert corr.sum() > 0
            pos                      = vals['mean'][corr]
            curr                     = vals['weight']/vals['weight'].sum()
            vect[ind:ind+corr.sum()] = pos - np.mean(pos)
            for j, k in enumerate(np.nonzero(corr)[0]):
                arr[ind+j,:]  = curr
                arr[ind+j,k] -= 1.
            ind += corr.sum()
        return ind

    def __addavgconstraint(self, good, arr):
        arr[0,:]  = np.sum(good, axis = 0)
        arr[0,:] *= self.beta/np.sum(arr[0,:])

    @staticmethod
    def __computecycles(good):
        rem       = [([i], np.copy(j)) for i, j in enumerate(good)]
        cycs      = [rem.pop()]
        pks, delt = cycs[-1]
        while len(rem):
            leftover = []
            for i, j in rem:
                if np.sum(j & delt) > 0:
                    pks.extend(i)
                    delt |= j
                else:
                    leftover.append((i,j))

            if len(leftover) == len(rem):
                cycs.append(leftover.pop())
                pks, delt = cycs[-1]

            rem = leftover
        return [i for i, _ in cycs]

    # pylint: disable=too-many-arguments
    def __addcycleconstraints(self, peaks, good, cycs, arr, vect):
        factor = self.alpha/sum(np.sum(good[j]) for j in cycs[0])
        cur    = np.zeros_like(arr[0,:])
        mean   = 0.
        for j in cycs[0]:
            cur[good[j]] += factor
            mean         += factor*peaks[j,:]['mean'].sum()

        vect[:] = mean
        for i, cycle in enumerate(cycs[1:]):
            factor    = self.alpha/sum(np.sum(good[j]) for j in cycle)
            arr [i,:] = cur
            for j in cycle:
                arr [i,:][good[j]] -= factor
                vect[i]            -= factor*peaks[j,:]['mean'].sum()
