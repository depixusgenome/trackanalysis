#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Creates a histogram from available events"
import itertools
from abc         import abstractmethod
from functools   import partial
from typing      import Dict, Tuple
import numpy as np

from utils import initdefaults

from .._core import emrunner, emscore  # pylint: disable = import-error

class EMFlagger:
    'flag peak corresponding to events'
    def __init__(self,**kwa):
        self.kwargs    = kwa
        self.mincount  = kwa.get("mincount",3)

    def __strip(self, params, events):
        '''
        assigns events to most likely peaks
        '''
        pos = np.array([ np.array([[np.nanmean(evt),len(evt)] for evt in cyc])
                         if cyc.size>0 else np.array([]) for cyc in events])
        predict = partial(self.__predict,params)
        ids     = np.array(list(map(predict,pos)))
        return params[:,0], ids

    @staticmethod
    def __predict(params:np.ndarray, data:np.ndarray):
        'return ids'
        if data.size==0:
            return np.array([])
        score = emscore(data,params).T
        return np.array([np.argmax(_) if max(_)>1e-4 else np.iinfo("i4").max for _ in score])

    def group(self,counts,params,events):
        'counts, estimated number of events per peak'
        keep   = counts > self.mincount
        params = params[keep]
        asort  = np.argsort(params[:,0])
        return self.__strip(params[asort],events)

class BaseEM(EMFlagger):
    """
    Base class for Expectation Maximization fitting algorithms
    """
    emiter      = 1000
    tol         = 1e-5  # loglikelihood tolerance
    withtime    = True
    precision   = 1e-5   # std deviation
    mergewindow = 0.00 # in microns

    @initdefaults(frozenset(locals()))
    def __init__(self,**kwa):
        super().__init__(**kwa)
        self.events = None
        self.data   = None
        self.fittingalgo = self.cfit

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

    @staticmethod
    def cfit(data,rates,params,emiter,tol,precision=1e-9): # pylint: disable = too-many-arguments
        'fitting using c calls'
        out = emrunner(data,rates,params,emiter,precision,tol)
        return out.rates, out.params

    @abstractmethod
    def find(self,**kwa):
        "finds best set of parameters"
        pass

    def __call__(self,**kwa):
        self.kwargs = kwa
        self.events = kwa.get("events",None)
        self.precision = kwa.get("precision",self.precision)
        if self.withtime:
            self.data  = np.array([[np.nanmean(evt),len(evt)]
                                   for cycle in self.events
                                   for evt in cycle])
        else:
            self.data = np.array([[np.nanmean(evt)]
                                  for cycle in self.events
                                  for evt in cycle])

        return self.find(**kwa)

    @staticmethod
    def score(data:np.ndarray,params:np.ndarray)->np.ndarray:
        'return the score[i,j] array corresponding to pdf(Xj|Zi, theta)'
        return emscore(data,params)

    def getdelta(self,dims):
        "delta value for a peak parameter"
        delta = np.array([0.001]*dims) # in microns
        delta[range(1,2,len(delta))] = 0.0 # no delta in cov
        if self.withtime:
            delta[-2:] = 0.0
        return delta

    def splitparams(self,rates,params,idx):
        """
        splits a peak in two
        """
        delta = self.getdelta(params.shape[1])
        nparams         = np.vstack([params[:idx+1],params[idx:]])
        nparams[idx]   -= delta
        nparams[idx+1] += delta
        nrates = np.vstack([rates[:idx+1],rates[idx:]])
        nrates[idx:idx+2] /=2
        return nrates,nparams

    def fit(self,data,rates,params):
        "call the fitting algo"
        return self.fittingalgo(data,
                                rates,
                                params,
                                self.emiter,
                                self.tol,
                                self.precision**2)

    def fromzestimate(self,data:np.ndarray,zpeaks:np.ndarray):
        "calls fittingalgo based on estimation of zpeaks"
        # group peaks too close
        zpeaks   = np.sort(zpeaks)
        tomerge  = np.where(np.diff(zpeaks)>self.mergewindow)[0]
        bins     = [min(data[:,0])]+[np.mean(zpeaks[i:i+2]) for i in tomerge]+[max(data[:,0])+0.1]

        # estimate rates, params using merged
        return self.paramsfromzbins(data,bins,mincount=1)

    def paramsfromzbins(self,data,bins,mincount=None):
        "given a list of bins along z axis, estimates the parameters"
        mincount  = self.mincount if mincount is None else mincount
        digi      = np.digitize(data[:,0].ravel(),bins)
        clas      = {idx:np.array([data[_1] for _1,_2 in enumerate(digi) if _2==idx])
                     for idx in set(digi)}
        params = np.vstack([list(itertools.chain.from_iterable(zip(np.nanmean(clas[idx],axis=0),
                                                                   np.nanvar(clas[idx],axis=0))))
                            for idx in set(digi)
                            if len(clas[idx])>mincount])
        if self.withtime:
            params[:,-2] = 0.
            params[:,-1] = [np.nanvar(clas[idx][-1])
                            for idx in set(digi)
                            if len(clas[idx])>mincount]
        rates = np.array([[len(clas[idx])] for idx in set(digi)
                          if len(clas[idx])>mincount])

        return rates/np.sum(rates),params
