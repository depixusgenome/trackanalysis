#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
    Computing the MLE for the probability of an hybridisation such that:

    #. It was observed at during at least Δ_{self.minduration} time
    #. It disappeared after a time nmax

    Consider the de-hibridization probability rho between measures n and n+1.
    Then:

    #. The probability of hybridisation lasting K measures is
       proportional to: p (1-p)^K
    #. The probability of hybridisation lasting until the end of the cycle
       is proportional to: (1-p)^N

    Normalizing them, we find: P(K) = p (1-p)^(K-D), P(N) = (1-p)^(N-D)
    where: D = Δ_{self.minduration}

    Where:

    * N_k is the number of events wich lasted k, reaching the cycle end
    * n_k is the number of events wich lasted k, not reaching the cycle end

    The maximum likelihood estimation (MLE) is:

         max_p(∏_k (p^{n_k} (1-p)^{(k-D) (n_k+N_k)}))

         <=> max(∑_k n_k log(p) + ∑_k (k-D) (n_k+N_k) log(1-p))
         <=> max((1-ρ) log(p) + (λ-D) log(1-p))

    where

        * ρ = ∑_k N_k / ∑_k (n_k + N_k)
        * λ = ∑_k (n_k + N_k) k / ∑_k (n_k + N_k)

         <=> p = (1-ρ)/(1-ρ-D + λ), after taking the derivative.

    For estimating the standard error, ρ and λ are considered
    to be independant variables, ρ following a binomial law and
    λ being the average of a geometric law.

    we then have : σ^2 ~ (p^2/(1-ρ))^2 σ_λ^2 + (p(1-p)/(1-ρ))^2 σ_ρ^2
    i.e.           σ^2 ~ p^2/(1-ρ)^2 (1-p)   + ρ/(1-ρ)^2 p^2 (1-p)^{N-D+2}(1-(1-p))^{N-D}

    as (1-p)^{N-D}(1-(1-p))^{N-D} <= 1/2^{N-D}  and N-D >> 1
                   σ   ~ p/(1-ρ) x sqrt(1-p)

    Moving back to time, with F the frame rate,
    we have (1-p)^{t*F} = exp(t * F ln(1-p)) ⇒ T = 1/(F ln(1-p))
"""
from    typing  import Union, Sequence
import  numpy   as np
from    utils   import initdefaults, EVENTS_TYPE
from    scipy.stats import skew as _skew

class Probability:
    "Computes probabilities"
    minduration   = 5
    framerate     = 30.
    nevents       = 0
    ncycles       = 0
    ntoolong      = 0
    totalduration = 0
    FMAX          = float(np.finfo('f4').max) # type: ignore
    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        pass

    def __apply(self, dur, last, maxdurs):
        self.nevents       += len(dur)
        self.ntoolong      += (last > maxdurs).sum()
        self.totalduration += np.sum(dur)

    def update(self,
               events : Sequence[Union[None, EVENTS_TYPE, Sequence[EVENTS_TYPE]]],
               maxdurs: Sequence[int]
              ) -> None:
        "Updates stats"
        arrs = np.array([isinstance(i, (list, np.ndarray)) for i in events], dtype = 'bool')
        if any(arrs):
            evts = events [arrs]
            dur  = [i['start'][-1]-i['start'][0]+len(i['data'][-1]) for i in evts]
            last = np.array([i['start'][-1]+len(i['data'][-1]) for i in evts],
                            dtype = 'i4')
            self.__apply(dur, last, maxdurs[arrs])

        arrs = np.array([isinstance(i, (tuple, np.void)) for i in events])
        if any(arrs):
            evts = events [arrs]
            dur  = np.array([len(i) for _, i in evts], dtype = 'i4')
            self.__apply(dur, dur + [i for i, _ in evts], maxdurs[arrs])

        self.ncycles += len(events)
        self.ncycles -= (events.discarded if hasattr(events, 'discarded') else # type: ignore
                         sum(getattr(i, 'discarded', 0) for i in events))

    @staticmethod
    def skew(events):
        "returns the skew of the population of points"
        arrs  = np.array([isinstance(i, (list, np.ndarray)) for i in events])
        skews = [_skew(np.concatenate(list(i['data']))) for i in events[arrs]]

        arrs  = np.array([isinstance(i, (tuple, np.void)) for i in events])
        if any(arrs):
            skews.extend(_skew(i[1]) for i in events[arrs])

        return skews

    @classmethod
    def positionprecision(cls, events):
        "returns the resolution"
        nevts = sum(1 for i in events if i is not None) - getattr(events, 'discarded', 0)
        return np.NaN if nevts <= 0 else cls.resolution(events)/np.sqrt(nevts)

    @staticmethod
    def resolution(events):
        "returns the resolution"
        arrs = np.array([isinstance(i, (list, np.ndarray)) for i in events])
        stds = [np.average([np.nanmean(j)    for j in i['data']],
                           weights = [len(j) for j in i['data']])
                for i in events[arrs]]

        arrs = np.array([isinstance(i, (tuple, np.void)) for i in events])
        if any(arrs):
            stds.extend(np.nanmean(i[1]) for i in events[arrs])

        return np.nanstd(stds)

    def __call__(self,
                 events : Sequence[Union[None, EVENTS_TYPE, Sequence[EVENTS_TYPE]]],
                 maxdurs: Sequence[int]
                ) -> 'Probability':
        "Returns an object containing stats related to provided events"
        obj = Probability(minduration = self.minduration,
                          framerate   = self.framerate)
        obj.update(events, maxdurs)
        return obj

    @property
    def good(self) -> bool:
        "Wether the probability is mathematically sound"
        if self.nevents <= 0:
            return False

        val = (self.totalduration-self.ntoolong)/self.nevents
        return self.minduration < 1.+ val

    @property
    def probability(self) -> float:
        "Off probability"
        if self.nevents <= self.ntoolong:
            return 0.

        mrho = 1.- self.ntoolong / self.nevents
        tmp  = mrho + self.totalduration/self.nevents
        return 0.  if tmp <= self.minduration else mrho/(tmp-self.minduration)

    @property
    def averageduration(self) -> float:
        "Average duration of an event"
        if self.nevents <= 0:
            return 0.

        return (self.totalduration/self.nevents) / self.framerate

    @property
    def likelyduration(self) -> float:
        "Average duration of an event computed with an MLE"
        if self.nevents <= 0:
            return 0.

        prob = 1.-self.probability
        if prob <= 0.:
            return 0.

        lnp = -np.log(prob)*self.framerate
        return self.FMAX if lnp <= 0. else 1./lnp if np.isfinite(lnp) else 0.

    @property
    def hybridisationrate(self) -> float:
        "Probability of observing a hybridisation"
        return 0. if self.ncycles <= 0 else min(1., self.nevents/self.ncycles)

    @property
    def stddev(self) -> float:
        "Standard deviation to the probability"
        if self.nevents <= 0:
            return 0.

        mrho = 1.- self.ntoolong / self.nevents
        tmp  = mrho + self.totalduration / self.nevents
        if tmp <= self.minduration:
            return 0.

        prob = mrho / (tmp-self.minduration)
        return prob / mrho * np.sqrt(1-prob)

    @property
    def uncertainty(self) -> float:
        "Measure uncertainty"
        if self.nevents <= self.ntoolong:
            return self.FMAX

        return self.likelyduration / np.sqrt(self.nevents-self.ntoolong)
