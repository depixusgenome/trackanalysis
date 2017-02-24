#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"""
    Computing the MLE for the probability of an hybridization such that:

    #. It was observed at during at least Δ_{self.minduration} time
    #. It disappeared after a time nmax

    Consider the de-hibridization probability rho between measures n and n+1.
    Then:

    #. The probability of hybridization lasting K measures is
       proportional to: p (1-p)^K
    #. The probability of hybridization lasting until the end of the cycle
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
import numpy as np
from utils import initdefaults

class Probability:
    u"Computes probabilities"
    minduration   = 5
    framerate     = 5
    nevents       = 0
    ntoolong      = 0
    totalduration = 0
    FMAX          = np.finfo('f4').max # type: ignore

    @initdefaults
    def __init__(self, **_):
        pass

    def __call__(self, events, maxdurs) -> 'Probability':
        u"Returns an object containing stats related to provided events"
        obj = Probability(minduration = self.minduration, framerate = self.framerate)
        for evts, maxdur in zip(events, maxdurs):
            if evts is None:
                continue

            if isinstance(evts, np.ndarray):
                last = evts[-1][0]+len(evts[-1][0])
                dur  = last - evts[0][0]
            else:
                last = evts[0]+len(evts[0])
                dur  = len(evts[1])

            if dur < self.minduration:
                continue

            obj.nevents       += 1
            obj.ntoolong      += last >= maxdur
            obj.totalduration += dur
        return obj

    @property
    def good(self) -> bool:
        u"Wether the probability is mathematically sound"
        if self.nevents <= 0:
            return False

        val = (self.totalduration-self.ntoolong)/self.nevents
        return self.minduration < 1.+ val

    @property
    def probability(self) -> float:
        u"Off probability"
        if self.nevents <= self.ntoolong:
            return 0.

        mrho = 1.- self.ntoolong / self.nevents
        tmp  = mrho + self.totalduration/self.nevents
        return 0.  if tmp <= self.minduration else mrho/(tmp-self.minduration)

    @property
    def averageduration(self) -> float:
        u"Average duration of an event"
        prob = 1.-self.probability
        if prob <= 0.:
            return 0.

        lnp = -np.log(prob)*self.framerate
        return self.FMAX if lnp <= 0. else 0. if np.isfinite(lnp) else 1./lnp

    @property
    def stddev(self) -> float:
        u"Standard deviation to the probability"
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
        u"Measure uncertainty"
        if self.nevents <= self.ntoolong:
            return self.FMAX

        return self.averageduration / np.sqrt(self.nevents-self.ntoolong)
