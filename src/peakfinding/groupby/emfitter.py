#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Creates a histogram from available events"
from typing import Iterable, List, Union
import numpy as np
from sklearn.mixture import GaussianMixture

from utils import initdefaults

from ._baseem import BaseEM
from .histogramfitter import ByHistogram

# need to clean up initialization of params

class MaxCov(BaseEM):
    '''
    finds peaks and groups events using Expectation Maximization
    peaks are subdivided until none have a covariance above uppercov
    '''
    uppercov   = 0.005**2 # in microns**2
    withtime   = True

    @initdefaults(frozenset(locals()))
    def __init__(self, **kwa):
        super().__init__(**kwa)
        self.fittingalgo = self.cfit

    def findfromzestimates(self,**kwa):
        "estimates starting parameters using kernel density"
        rates, params = self.kernelinitializer(**kwa)
        return self.splitter(rates,params)[-2:]

    def find(self, **kwa):
        """
        find peaks along z axis
        keyword arguments are :
        hist,
        events,
        pos,
        precision, hf sigma
        """
        rates, params = self.findfromzestimates(**kwa)
        peaks, ids    = self.group(rates.ravel()*self.data.shape[0],params,self.events)
        return peaks, ids


    def kernelinitializer(self,**kwa):
        'uses ZeroCrossing for initialization faster'
        peaks,ids = ByHistogram(**self.kwargs)(**kwa)
        # include mergewindow and replace ids
        rpl = np.hstack([np.argwhere(np.diff(peaks)>self.mergewindow).ravel(),len(peaks)-1])
        digits = np.hstack(ids)
        for idx in range(len(peaks)):
            digits[digits==idx]=rpl[rpl>=idx][0]
        # mean peaks are updated
        rates,params = self.paramsfromdigits(self.data,digits,self.mincount)
        return rates,params

    def splitter(self,*args):
        """
        splits the peaks if bic is better
        args: rates, params
        """
        return self._splitwidth(*args)

    def _splitwidth(self,*args):
        'splits the peaks with great Z variance'
        rates, params = self.fit(self.data,*args) # pylint: disable =no-value-for-parameter

        while any(params[:,1]>self.uppercov):
            idx = np.argmax(params[:,1])
            # split the one with highest covariance
            nrates,nparams = self.splitparams(rates,params,idx)
            # could be improved by reducing the number of peaks (and associated data)
            # to optimized during emstep
            rates, params = self.fit(self.data,nrates,nparams)
        return rates,params


class ByGauss(MaxCov):
    '''
    finds peaks and groups events using Expectation Maximization
    uses sklearn EM implementation
    '''
    fitter:GaussianMixture
    withtime = False
    @initdefaults(frozenset(locals()))
    def __init__(self, **kwa):
        super().__init__(**kwa)
        self.fittingalgo = self.skfit # check correct initialization

    @staticmethod
    def skfit(data,rates,params,emiter:int):
        "wraps call to sklearn fitter"
        gaussfitter = GaussianMixture(n_components = params.shape[0],
                                      means_init=params[:,0].reshape(-1,1),
                                      covariance_type="diag",
                                      weights_init=rates.ravel(),
                                      max_iter=emiter,
                                      precisions_init=1/params[:,1].reshape(-1,1)\
        ).fit(data)
        return gaussfitter.weights_.reshape(-1,1),\
            np.hstack([gaussfitter.means_,gaussfitter.covariances_])


class RandInit(BaseEM):
    """
    starting positions of peaks are chosen randomly
    used for demo and testing selection criteria
    if nsamples is not specified estimates number of peaks from kerneldensity
    """
    nsamples : Union[int,Iterable[int]] = None
    repeats  = 10
    withtime = True
    @initdefaults(frozenset(locals()))
    def __init__(self, **kwa):
        self.fittingalgo = self.cfit
        super().__init__(**kwa)

    def find(self,**kwa):
        "initializes with n different samples from data"
        if self.nsamples is None:
            self.nsamples  = len(ByHistogram(**self.kwargs)(**kwa)[0])

        rates, params = self.fitnsamples()
        peaks, ids    = self.group(rates.ravel()*self.data.shape[0],params,self.events)

        return peaks, ids

    def nrandinit(self,nsamples:int):
        """
        returns the randomly initialized rates, params with lower bic
        """
        inits = [np.random.choice(self.data[:,0],nsamples) for i in range(self.repeats)]
        bicpeaks = []
        for peaks in inits:
            rates,params = self.fromzestimate(self.data,peaks)
            rates,params = self.fit(self.data,rates,params)
            score        = self.score(self.data,params)
            bic          = self.bic(score,rates,params)
            bicpeaks.append((bic,rates,params))

        return sorted(bicpeaks,key=lambda x:x[0])[0]

    def fitnsamples(self):
        "returns the best fit across multiple samples"
        if isinstance(self.nsamples,Iterable):
            return sorted([self.nrandinit(_) for _ in self.nsamples],
                          key=lambda x: x[0])[0][-2:]

        return self.nrandinit(self.nsamples)[-2:]

class BicSplit(MaxCov):
    """
    tries to split each peak iteratively
    keeps splitting until the bic is worse
    """

    def __tocheck(self,rates,tocheck)-> List[bool]:
        """
        must returns mutable list of bools.
        """
        enough = np.round(self.data.shape[0]*rates.ravel())>self.mincount*2
        return list(np.logical_and(enough,tocheck))

    def splitter(self,*args):
        "splits the peaks if bic is better"
        return self._splitwithbic(*args)

    def _splitwithbic(self,*args):
        rates, params = self.fit(self.data,*args) # pylint: disable=no-value-for-parameter
        tocheck       = self.__tocheck(rates,params[:,1]>self.precision**2)
        bic           = self.bic(self.score(self.data,params),rates,params)
        while any(tocheck):
            idx = next(i for i,v in enumerate(tocheck) if v)
            nrates,nparams = self.splitparams(rates,params,idx)
            nrates,nparams = self.fit(self.data,nrates,nparams)
            nbic = self.bic(self.score(self.data,nparams),nrates,nparams)
            if nbic<bic:
                bic,rates,params = nbic,nrates,nparams
                tocheck          = np.insert(tocheck,idx,True)
                # updating
                tocheck          = self.__tocheck(rates,params[:,1]>self.precision**2)
            else:
                tocheck[idx] = False

        return rates,params


class FullEm(BicSplit):
    """
    Covariance of parameters should have upper and lower boundaries.
    Upper covariance boundaries are set and each parameter is subdivided using MaxCov
    First calls MaxCov splitter to make sure that covariances parameters have an upper bound
    then calls SplitBic.splitter to ensure than one should not further divide peaks
    """
    def splitter(self,*args):
        return self._splitwithbic(*self._splitwidth(*args))
