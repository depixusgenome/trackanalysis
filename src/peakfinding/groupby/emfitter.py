#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Creates a histogram from available events"

import itertools
from itertools import chain
from functools import partial
from typing    import Dict, Tuple

import numpy as np

from utils            import initdefaults
from utils.logconfig  import getLogger
from .._core          import emrunner, emscore # pylint: disable = import-error
from .histogramfitter import ByHistogram # pylint: disable               = unused-import

LOGS = getLogger(__name__)

class ByEM: # pylint: disable=too-many-public-methods
    '''
    finds peaks and groups events using Expectation Maximization
    the number of components is estimated using BIC criteria
    '''
    emiter   = 100
    mincount = 5
    tol      = 0.5  # loglikelihood tolerance
    decimals = 4    # rounding values
    floaterr = 1e-10
    params  : np.ndarray
    rates   : np.ndarray
    minpeaks  = 1
    kwa : Dict = {}

    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        pass

    def __call__(self,**kwa):
        _, bias, slope = kwa.get("hist",(0,0,1))
        self.kwa = kwa
        return bias,slope #self.find(kwa.get("events",None), bias, slope, kwa["precision"])

    # to keep
    # def find(self, events, bias, slope, precision=None):
    #     'find peaks along z axis'
    #     data       = np.array([[np.nanmean(evt),len(evt)]
    #                            for cycle in events
    #                            for evt in cycle])
    #     maxpeaks   = int((max(data[:,0])-min(data[:,0]))//precision)
    #     #search     = self.search()
    #     #params     = search[-1]
    #     asort      = np.argsort(params[:,0,0])
    #     peaks, ids = self.__strip(params[asort],events)
    #     return peaks * slope + bias , ids

    def __strip(self, params, events):
        '''
        then assigns events to most likely peaks
        '''
        pos = np.array([ np.array([[np.nanmean(evt),len(evt)] for evt in cyc])
                         if cyc.size>0 else np.array([]) for cyc in events])

        predict = partial(self.__predict,params)
        ids     = np.array(list(map(predict,pos)))
        return params[:,0,0], ids

    def __predict(self, params:np.ndarray, data:np.ndarray):
        if data.size==0:
            return np.array([])
        score = self.score(data,params).T
        ids   = [np.argmax(_) if max(_)>1e-4 else np.iinfo("i4").max for _ in score]
        return np.array(ids)

    def initialize(self,data:np.ndarray,maxbins:int=1)->np.ndarray:
        'initialize using density'
        bins      = np.histogram(data[:,0],bins=maxbins)[1]
        bins[-1] += 0.1
        digi      = np.digitize(data[:,:-1].ravel(),bins)
        clas      = {idx:np.array([data[_1] for _1,_2 in enumerate(digi) if _2==idx])
                     for idx in set(digi)}
        params = np.vstack([list(chain.from_iterable(zip(np.nanmean(clas[idx],axis=0),
                                                         np.nanvar(clas[idx],axis=0))))
                            for idx in set(digi)
                            if len(clas[idx])>self.mincount])
        params[:,-2] = 0.
        params[:,-1] = [np.nanstd(clas[idx][-1])
                        for idx in set(digi)
                        if len(clas[idx])>self.mincount]

        return 1/len(params)*np.ones((len(params),1)) , params

    @staticmethod
    def score(data:np.ndarray,params:np.ndarray)->np.ndarray:
        'return the score[i,j] array corresponding to pdf(Xj|Zi, theta)'
        return emscore(data,params)

    @classmethod
    def assign(cls,score:np.ndarray)->Dict[int,Tuple[int, ...]]:
        'to each event (row in data) assigns a peak (row in params)'
        # Gaussian distribution for position, exponential for duration
        # score[j,i] = pdf(Xi|Zj, theta)
        assigned = sorted([(np.argmax(row),idx) for idx,row in enumerate(score.T)])
        out : Dict[int,Tuple[int, ...]] = {_:tuple() for _ in range(score.shape[0])}
        out.update({key: tuple(i[1] for i in grp)
                    for key,grp in itertools.groupby(assigned,lambda x:x[0])})
        return out

    def bic(self,score:np.ndarray,rates:np.ndarray,params:np.ndarray)->float:
        'returns bic value'
        llikeli = self.llikelihood(score,rates)
        return -2*llikeli + params.size *np.log(0.5*score.shape[1]/np.pi)

    def aic(self,score:np.ndarray,rates:np.ndarray,params:np.ndarray)->float:
        'returns aic value'
        return 2*params.size -2*self.llikelihood(score,rates)

    @classmethod
    def llikelihood(cls,score:np.ndarray,rates:np.ndarray)->float:
        'returns loglikelihood'
        return np.sum(np.log(np.sum(rates*score,axis=0)))

    def cfit(self,data,rates,params,bounds=(10**2,0.001**2)):
        'fitting using c calls'
        out = emrunner(data,rates,params,self.emiter,bounds[0],bounds[1])
        return out.score, out.rates, out.params

    @classmethod
    def __rmduplicates(cls,params,rates):
        '''
        this removes only using z coordinates, but
        removing duplicates requires extension to t (and x, y if available)
        until then leads to incorrect convergence
        '''
        rounded    = enumerate(zip(np.round(np.hstack(params[:,0,0]),decimals=cls.decimals),rates))
        sortedinfo = sorted(((*val,idx) for idx,val in rounded),key=lambda x:(x[0],-x[1]))
        return list(map(lambda x:next(x[1])[-1],itertools.groupby(sortedinfo,key=lambda x:x[0])))

    def splitter(self,data,rates,params,upper_bound=0.005**2):
        'splits the peaks with great Z variance'
        delta = np.array([0.001]*params.shape[1]) # in microns
        delta[-2:] = 0.0
        delta[range(1,2,len(delta))] = 0.0 # no delta in cov
        score, rates, params = self.cfit(data,rates,params)
        while any(params[:,1]>upper_bound):
            idx = np.argmax(params[:,1])
            # split the one with highest covariance
            nparams         = np.vstack([params[:idx+1],params[idx:]])
            nparams[idx]   -= delta
            nparams[idx+1] += delta
            nrates = np.vstack([rates[:idx+1],rates[idx:]])
            nrates[idx:idx+2] /=2
            # could be improved by reducing the number of peaks (and associated data)
            # to optimized during emstep
            score, rates, params = self.cfit(data,nrates,nparams)
        return score,rates,params
