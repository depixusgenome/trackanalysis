#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Collapse intervals. The idea is to measure the behaviour common to all
stretches of data. This should be removed as it's source is either a (thermal,
electric, ...) drift or a mechanical vibration.
"""
from    typing          import (Optional, Union,
                                Callable, NamedTuple, Sequence, Iterable,
                                Tuple, Iterator, cast)
from    enum            import Enum
from    functools       import partial
import  pandas
import  numpy as np
from    utils           import initdefaults
from    signalfilter    import Filter

Range   = NamedTuple('Range', [('start', int), ('values', np.ndarray)])

class Profile:
    "A bead profile: the behaviour common to all stretches of data"
    def __init__(self, inter:Union[Sequence[Range], 'Profile', int]) -> None:
        if isinstance(inter, (int, cast(type, np.integer))):
            self.xmin: int = 0
            self.xmax: int = cast(int, inter)
        elif isinstance(inter, Profile):
            self.xmin = cast(int, inter.xmin)
            self.xmax = cast(int, inter.xmax)
        else:
            self.xmin = min(i.start               for i in inter)
            self.xmax = max(i.start+len(i.values) for i in inter)

        length     = self.xmax-self.xmin
        self.count = np.zeros((length,), dtype = np.int32)
        self.value = np.zeros((length,), dtype = np.float32)

    def fit(self, rng:Range):
        "returns the range with values fit to the profile"
        ix1  = rng[0] - self.xmin
        ix2  = ix1 + len(rng[1])
        inds = self.count[ix1:ix2] > 0
        mean = np.nanmean(self.value[ix1:ix2][inds]-rng[1][inds])
        return Range(rng[0], rng[1]+mean)

    def subtracted(self, rng:Range):
        "returns the range with values fit to the profile"
        ix1 = rng[0] - self.xmin
        ix2 = ix1 + len(rng[1])
        return Range(rng[0], rng[1]-self.value[ix1:ix2])

    def __len__(self):
        return len(self.count)

def _iter_ranges(xmin:int, inter:Sequence[Range]) -> Iterable[Tuple[np.ndarray, np.ndarray]]:
    for rng in inter:
        if len(rng.values) == 0 or rng.start+len(rng.values) <= xmin:
            continue

        vals = rng.values[max(xmin-rng.start, 0):]
        good = np.isfinite(vals)
        if any(good):
            good = np.nonzero(good)[0]
            yield (good+max(rng.start-xmin, 0), vals[good])

class _CollapseAlg:
    "base class for collapse. Deals with stitching as well"
    edge:   int    = 1
    filter: Filter = None
    @initdefaults(frozenset(locals()))
    def __init__(self, **kwa):
        pass

    @property
    def _edge(self):
        return None if self.edge is None or self.edge < 1 else int(self.edge)

    def __call__(self,
                 inter     : Iterable[Range],
                 prof      : Profile = None,
                 precision : float   = None) -> Profile:
        if isinstance(inter, Iterator):
            inter = tuple(inter)
        inter = cast(Sequence[Range], inter)
        prof  = Profile(inter) if prof is None else prof
        return self._run(inter, prof, precision)

    def _run(self, inter:Sequence[Range], prof:Profile, precision:Optional[float]) -> Profile:
        raise NotImplementedError()

    @classmethod
    def run(cls, inter:Iterable[Range], **kwa) -> Profile:
        "creates the configuration and runs the algorithm"
        return cls(**kwa)(inter)

    def totable(self, inter:Sequence[Range], prof:Profile = None) -> np.ndarray:
        "collapse intervals to a table"
        if isinstance(inter, Iterator):
            inter = tuple(inter)
        prof  = Profile(inter) if prof is None else prof
        return self._totable(inter, prof)

    @classmethod
    def __occupation(cls, inter:Sequence[Range], xmin:int, xmax:int) -> np.ndarray:
        "returns the number of overlapping intervals in the [xmin, xmax] range"
        ret = np.zeros((xmax-xmin,), dtype = np.int32)
        for rng in inter:
            ret[max(rng.start-xmin,0) : max(rng.start+len(rng.values)-xmin, 0)] += 1
        return ret

    def _totable(self, inter:Sequence[Range], prof:Profile) -> np.ndarray:
        "collapse intervals to a table"
        prof  = Profile(inter) if prof is None else prof
        vals  = np.full((prof.count.shape[0],
                         max(self.__occupation(inter, prof.xmin, prof.xmax))),
                        np.NaN,
                        dtype = np.float32)
        cnt   = np.zeros_like(prof.count)
        occ   = prof.count
        inner = slice(self._edge, None)

        # compactify all derivatives into a single 2D table
        # missing values are coded as NaN
        for inds, cur in _iter_ranges(prof.xmin, inter):
            if len(inds) == 0:
                continue

            vals[inds, max(cnt[inds])] = cur
            cnt[inds]                 += 1
            occ[inds[inner]]          += 1
        return vals

class CollapseToMean(_CollapseAlg):
    """
    Collapses intervals together using their mean values.

    The collapse starts from the right-most interval and moves left.
    """
    PRECISION                          = 0.003
    weight: Union[Callable, None, str] = None
    measure                            = 'mean'
    @initdefaults(frozenset(locals()))
    def __init__(self, **kwa):
        super().__init__(**kwa)

    @staticmethod
    def _chisquare(prec, _, vals) -> float:
        if len(vals) <= 5:
            return 1e-3
        chis = (vals-vals.mean())/prec
        chis*= chis
        val  = chis.sum()/(len(chis)-1.)
        return 1./max(min(val, 1e3), 1e-3)

    def _weight_function(self, _, precision) -> Callable[[np.ndarray, np.ndarray], float]:
        if callable(self.weight):
            return self.weight

        if self.weight is None:
            return lambda *_: 1

        if self.weight == 'chisquare':
            fcn = partial(self._chisquare, self.PRECISION if precision is None else precision)
            return cast(Callable[[np.ndarray, np.ndarray], float], fcn)

        fcn = getattr(np, self.weight)
        return lambda _, i: fcn(i)

    def _run(self, inter:Sequence[Range], # pylint: disable=too-many-locals
             prof:Profile, precision: float = None) -> Profile:
        key    = lambda i: (-i.start-len(i.values), -len(i.values))
        cnt    = np.array(prof.count, dtype = 'f4')
        edge   = self._edge
        inner  = slice(edge, None if edge is None else -edge)
        diff   = getattr(np, self.measure)

        weight = self._weight_function(prof, precision)
        for inds, cur in _iter_ranges(prof.xmin, sorted(inter, key = key)):
            rho                      = cnt[inds]*1.
            vals                     = prof.value[inds]

            if any(rho):
                cur                 += diff((vals-cur)[rho>0])
                wcur                 = weight(inds, cur)
                rho                 /= rho+wcur
                prof.value[inds]     = rho*vals + (1.-rho)*cur
            else:
                cur                 -= diff(cur)
                wcur                 = weight(inds, cur)
                prof.value[inds]     = cur*wcur

            cnt       [inds]        += wcur
            prof.count[inds[inner]] += 1

        if callable(self.filter):
            self.filter(prof.value)     # pylint: disable=not-callable
        return prof

class CollapseToSock(CollapseToMean):
    "Collapses twice, the second time using first results to discard faulty events"
    robustness  = .1, .9
    weight: str = 'robustmean'
    @staticmethod
    def _chisquare(prec, prof, inds, vals): # pylint: disable=arguments-differ
        if len(vals) <= 5:
            return 1e-3
        good = prof.count[inds] > 0
        chis = (vals[good]-prof.value[inds[good]])/prec
        chis*= chis
        val  = np.nanmean(chis)
        return 1./max(min(val, 1e3), 1e-3)

    def __fromsock(self, cpy, inter, prof):
        table = self._totable([cpy.fit(i) for i in inter], cpy)
        cnt   = np.sum(np.isfinite(table), axis = 1)
        good  = cnt > 0
        table = table[good]

        prof.value[:] = 0
        prof.count    = cpy.count

        if self.weight == 'median':
            prof.value[good] = np.nanmedian(table, axis = 1)
        else:
            table     = np.sort(table, axis = 1)
            inds      = np.round(np.outer(cnt[good], self.robustness))
            inds[:,1] = np.minimum(inds[:,1]+1, cnt[good])
            inds      = np.int32(inds) #type: ignore
            prof.value[good] = [vals[i:j].mean() for vals, (i, j) in zip(table, inds)]

        return prof

    def _run(self, inter:Sequence[Range], prof:Profile, precision: float = None) -> Profile:
        if self.weight is None:
            return super().__call__(inter, prof, precision)

        precision = self.PRECISION if precision is None else precision
        cnf       = CollapseToMean(**self.__dict__)

        cnf.weight = None
        cpy        = cnf(inter, Profile(prof), precision)
        if self.weight in ('median', 'robustmean'):
            return self.__fromsock(cpy, inter, prof)

        if self.weight == 'chisquare':
            cpy.value[cpy.count <= 0] = np.NaN
            cnf.weight                = partial(self._chisquare, precision, cpy)
        else:
            cnf.weight                = self.weight
        return cnf(inter, prof, precision)

class CollapseByMerging(_CollapseAlg):
    """
    Collapses intervals together using their mean values

    The collapse is done by merging intervals sharing the maximum number of points.
    """
    @staticmethod
    def __init_inters(inter):
        inters = []
        for start, vals in inter:
            fin = np.isfinite(vals)
            inters.append((start,
                           np.where(fin, vals, 0.) - np.nanmean(vals),
                           np.int32(fin)))
        return inters

    @staticmethod
    def __compute_commons(common, rngs, i):
        cur  = common[:,i]
        rng  = rngs[i]

        np.minimum (rngs[:,1], rng[1],                        out = cur)
        np.subtract(cur,       np.maximum(rngs[:,0], rng[0]), out = cur)
        np.maximum (cur,       0,                             out = cur)
        cur[i] = 0

    @classmethod
    def __init_common(cls, inters):
        rngs   = np.array([[start, start+len(vals)] for start, vals, _ in inters])
        common = np.zeros((len(rngs), len(rngs)), dtype = 'i4')
        for i in range(len(rngs)):
            cls.__compute_commons(common, rngs, i)
        return rngs, common

    @staticmethod
    def __delta(rng1, rng2):
        start  = rng1[0], rng2[0]
        stop   = rng1[0]+len(rng1[1]), rng2[0]+len(rng2[1])

        sli    = slice(max(*start)-start[0], min(*stop)-start[0])
        both   = np.isfinite(rng1[1][sli])
        return rng1[1][sli][both][rng1[2][sli][both] > 0].mean()

    @classmethod
    def __merge(cls, rng1, rng2):
        start     = min(rng1[0], rng2[0])
        stop      = max(rng1[0]+len(rng1[1]), rng2[0]+len(rng2[1]))

        sl1       = slice(rng1[0]-start, rng1[0]-start + len(rng1[2]))
        sl2       = slice(rng2[0]-start, rng2[0]-start + len(rng2[2]))

        cnt       = np.zeros((stop-start,), dtype = 'i4')
        cnt[sl1]  = rng1[2]
        cnt[sl2] += rng2[2]

        rho       = np.zeros((stop-start,), dtype = 'f4')
        rho[sl1]  = rng1[2]
        rho      /= cnt

        vals        = np.copy(rho)
        vals[sl1]  *=  rng1[1] - cls.__delta(rng1, rng2)
        vals[sl2]  += (rng2[1] - cls.__delta(rng2, rng1)) * (1.-rho[sl2])
        return start, vals, cnt

    def __update_prof(self, prof, inters, rngs):
        for i, rng in enumerate(rngs):
            if rng[0] == rng[1]:
                continue

            start, vals, cnt = inters[i]
            ix1  = max(start, prof.xmin)
            ix2  = min(start+len(vals), prof.xmax)
            prof.value[ix1-prof.xmin:ix2-prof.xmin] = vals[ix1-start:ix2-start]

            ix1 += self.edge or 0
            ix2 -= self.edge or 0
            if ix2 > ix1:
                prof.count[ix1-prof.xmin:ix2-prof.xmin] = cnt [ix1-start:ix2-start]

    def _run(self, inter:Sequence[Range], prof:Profile, _) -> Profile:
        inters       = self.__init_inters(inter)
        rngs, common = self.__init_common(inters)
        ncols        = common.shape[1]

        for _ in range(len(inters)-1):
            imax = np.argmax(common)
            ind  = imax // ncols, imax % ncols
            if common[ind[0],ind[1]] <= 0:
                break

            start, vals, cnt = self.__merge(inters[ind[0]], inters[ind[1]])

            inters[ind[0]] = start, vals, cnt
            rngs  [ind[0]] = start, start + len(vals)
            rngs  [ind[1]] = 0, 0

            self.__compute_commons(common, rngs, ind[0])
            common [ind[1],:] = 0
            common [:,ind[1]] = 0

        self.__update_prof(prof, inters, rngs)

        if callable(self.filter):
            self.filter(prof.value) # pylint: disable=not-callable
        return prof

class DerivateMode(Enum):
    "Computation modes for the derivative method."
    median = 'median'
    mean   = 'mean'

class CollapseByDerivate(_CollapseAlg):
    """
    Behaviour common to all is measured using the distribution of derivatives at
    each time frame. Either the mean or the median is defined as the profile
    derivative.
    """
    maxder: float                    = np.inf
    mode:   Union[str, DerivateMode] = 'median'
    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        super().__init__(**_)

    def __setstate__(self, kwa):
        self.__init__(**kwa)

    @classmethod
    def __occupation(cls, inter:Sequence[Range], xmin:int, xmax:int) -> np.ndarray:
        "returns the number of overlapping intervals in the [xmin, xmax] range"
        ret = np.zeros((xmax-xmin,), dtype = np.int32)
        for rng in inter:
            ret[max(rng.start-xmin,0) : max(rng.start+len(rng.values)-xmin, 0)] += 1
        return ret

    def totable(self, inter:Sequence[Range], prof:Profile = None) -> Tuple[np.ndarray,...]:
        "collapse intervals to a table"
        if isinstance(inter, Iterator):
            inter = tuple(inter)
        prof  = Profile(inter) if prof is None else prof
        return self._totable(inter, prof)

    def _totable(self, inter:Sequence[Range], prof:Profile) -> Tuple[np.ndarray,...]:
        "collapse intervals to a table"
        prof  = Profile(inter) if prof is None else prof
        vals  = np.full((prof.count.shape[0],
                         max(self.__occupation(inter, prof.xmin, prof.xmax))),
                        np.inf,
                        dtype = np.float32)
        cnt   = np.zeros_like(prof.count)
        occ   = prof.count
        inner = slice(self._edge, None)

        # compactify all derivatives into a single 2D table
        # missing values are coded as NaN
        for inds, cur in _iter_ranges(prof.xmin, inter):
            sel  = np.where(np.diff(inds) == 1)
            inds = inds[sel]
            if len(inds) == 0:
                continue

            vals[inds, max(cnt[inds])] = tuple(cur[i]-cur[i+1] for i in sel)
            cnt[inds]                 += 1
            occ[inds[inner]]          += 1

        vals[vals >= self.maxder] = np.NaN
        return vals, cnt

    def _run(self, inter:Sequence[Range], prof:Profile, _) -> Profile:
        vals, cnt           = self._totable(inter, prof)
        vals[:,0][cnt == 0] = 0 # suppress all NaN warning

        fcn    = getattr(np, 'nan'+DerivateMode(self.mode).value)
        values = fcn(vals, axis = 1)
        if callable(self.filter):
            self.filter(values)     # pylint: disable=not-callable
        prof.value = pandas.Series(values[::-1]).cumsum().values[::-1]
        return prof

CollapseAlg = Union[CollapseByDerivate, CollapseToMean, CollapseByMerging]
