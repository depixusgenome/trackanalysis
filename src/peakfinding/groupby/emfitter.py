#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Creates a histogram from available events"
import itertools
import warnings
from typing      import Union, Iterable
import numpy as np
from sklearn.mixture import GaussianMixture

from utils import initdefaults

from .._core import empz_x  # pylint: disable = import-error

from .histogramfitter import ByHistogram
from ._baseem import BaseEM

# needs a new splitter algorithm.
# if a peak needs splitting,
# subselect assigned data and
# do an EM fit on the subset (should at least be faster)
# split local?


class ByEM(BaseEM):
    '''
    finds peaks and groups events using Expectation Maximization
    the number of components is estimated using BIC criteria
    '''
    decimals   = 4     # rounding values
    upperbound = 0.005**2 # in microns**2
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
        # _, bias,slope = kwa.get("hist",(np.array([]),0,1))
        # return peaks * slope + bias , ids
        return peaks, ids


    def kernelinitializer(self,**kwa):
        'uses ZeroCrossing for initialization faster'
        peaks  = ByHistogram(**self.kwargs)(**kwa)[0]
        return self.fromzestimate(self.data,peaks)

    @classmethod
    def rmduplicates(cls,params,rates):
        '''
        this removes only using z coordinates, but
        removing duplicates requires extension to t (and x, y if available)
        until then leads to incorrect convergence
        '''
        rounded    = enumerate(zip(np.round(np.hstack(params[:,0,0]),decimals=cls.decimals),rates))
        sortedinfo = sorted(((*val,idx) for idx,val in rounded),key=lambda x:(x[0],-x[1]))
        return list(map(lambda x:next(x[1])[-1],itertools.groupby(sortedinfo,key=lambda x:x[0])))

    # could split all parameters with upper bound too high
    def splitter(self,rates,params):
        'splits the peaks with great Z variance'
        warnings.warn("using this function, with a symmetric splitting is not a good idea")
        rates, params = self.fit(self.data,
                                 rates,
                                 params)

        while any(params[:,1]>self.upperbound):
            idx = np.argmax(params[:,1])
            # split the one with highest covariance
            nrates,nparams = self.splitparams(rates,params,idx)
            # could be improved by reducing the number of peaks (and associated data)
            # to optimized during emstep
            rates, params = self.fit(self.data,nrates,nparams)
        return rates,params

class ByEmMutu(ByEM):
    ''' uses mutual information theory to decide whether peaks should be splitted or not'''

    @staticmethod
    def mutualinformation(score:np.ndarray,
                          rates:np.ndarray):
        '''
        computes the mutual information of the peaks
        if element i,j has >0 then  i,j are dependent (i.e. represents the same data)
        '''
        pz_x = np.matrix(empz_x(score,rates))
        pij  = np.array(pz_x*pz_x.T)/pz_x.shape[1]
        return pij*np.log2( (pij/np.mean(pz_x,axis=1)).T/np.mean(pz_x,axis=1) )

    def isbetter(self,score:np.ndarray,rates:np.ndarray)->bool:
        '''
        defines condition on mutualinformation
        returns True if peaks are better split,
        False otherwise
        '''
        info    = self.mutualinformation(score,rates)
        offdiag = np.array([info[i] for i in zip(*np.triu_indices_from(info,k=1))])
        if any(offdiag>-1e-4):
            return False
        return True

    def mutualsplit(self,rates,params):
        '''
        splits the peaks with great Z variance
        if mutual information allows keep the split of peaks
        '''
        rates, params = self.fit(self.data,rates,params)
        notchecked = np.array([True]*params.shape[0])

        while any(notchecked):
            print(f"params.shape={params.shape}")
            for idx in (i for i,j in enumerate(notchecked) if j):
                nrates,nparams = self.splitparams(rates,params,idx)

                # thermalise, thermalise only the splitted peaks to save time
                nrates,nparams = self.fittingalgo(self.data,
                                                  nrates,
                                                  nparams,
                                                  self.emiter,
                                                  self.tol,
                                                  self.precision)
                sco = self.score(self.data,nparams[[idx,idx+1]])

                # check mutual information
                if self.isbetter(sco,nrates[[idx,idx+1]]):
                    notchecked   = np.insert(notchecked,idx,True)
                    rates,params = nrates,nparams
                    break
                notchecked[idx]=False

        return rates,params


class ByGauss(ByEM):
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
    repeats = 10
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
