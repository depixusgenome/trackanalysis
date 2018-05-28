#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Creates a histogram from available events"
import itertools
import warnings
from abc         import abstractmethod
from functools   import partial
from typing      import Dict, Tuple, Union, Iterable
from collections import Sequence
import numpy as np
from sklearn.mixture import GaussianMixture

from utils import initdefaults

from .._core import (empz_x,emrunner,emscore)  # pylint: disable = import-error

from .histogramfitter import ByHistogram  # pylint: disable = unused-import

# needs cleaning

# needs a new splitter algorithm.
# if a peak needs splitting,
# subselect assigned data and
# do an EM fit on the subset (should at least be faster)
# split local?

class EMFlagger:
    'flag peak corresponding to events'
    withtime=True
    def __init__(self,**kwa):
        self.kwargs   = kwa
        self.mincount = kwa.get("mincount",5)
        self.events   = None
        self.data     = None

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

    @abstractmethod
    def find(self,**kwa):
        "finds best set of parameters"
        pass

    def __call__(self,**kwa):
        self.kwargs = kwa
        self.events = kwa.get("events",None)
        if self.withtime:
            self.data  = np.array([[np.nanmean(evt),len(evt)]
                                   for cycle in self.events
                                   for evt in cycle])
        else:
            self.data = np.array([[np.nanmean(evt)]
                                  for cycle in self.events
                                  for evt in cycle])

        return self.find(**kwa)

# make a base class common to ByEM, ByEmMutu, ByEMfromKernel
class ByEM(EMFlagger): # needs cleaning
    '''
    finds peaks and groups events using Expectation Maximization
    the number of components is estimated using BIC criteria
    '''
    emiter     = 1000
    tol        = 1e-5  # loglikelihood tolerance # need to provide to c code
    decimals   = 4     # rounding values
    upperbound = 0.005**2 # in microns**2
    mergewindow = 0.005
    withtime = True
    @initdefaults(frozenset(locals()))
    def __init__(self, **kwa):
        self.fittingalgo = self.cfit
        super().__init__(**kwa)

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

    def fromzestimate(self,data:np.ndarray,zpeaks:np.ndarray):
        "calls fittingalgo based on estimation of zpeaks"
        # group peaks too close
        zpeaks   = np.sort(zpeaks)
        tomerge  = np.where(np.diff(zpeaks)>self.mergewindow)[0]
        bins     = [min(data[:,0])]+[np.mean(zpeaks[i:i+2]) for i in tomerge]+[max(data[:,0])+0.1]

        # estimate rates, params using merged
        return self.paramsfromzbins(data,bins,mincount=0)

    def paramsfromzbins(self,data,bins,mincount=None):
        "given a list of bins along z axis, estimates the parameters"
        mincount  = self.mincount if mincount is None else mincount
        digi      = np.digitize(data[:,0].ravel(),bins)
        clas      = {idx:np.array([data[_1] for _1,_2 in enumerate(digi) if _2==idx])
                     for idx in set(digi)}
        params = np.vstack([list(itertools.chain.from_iterable(zip(np.nanmean(clas[idx],axis=0),
                                                                   np.nanvar(clas[idx],axis=0))))
                            for idx in set(digi)
                            if len(clas[idx])>self.mincount])
        if self.withtime:
            params[:,-2] = 0.
            params[:,-1] = [np.nanstd(clas[idx][-1])
                            for idx in set(digi)
                            if len(clas[idx])>self.mincount]
        rates = np.array([[len(clas[idx])] for idx in set(digi)
                          if len(clas[idx])>self.mincount])

        return rates/np.sum(rates),params

    def kernelinitializer(self,**kwa):
        'uses ZeroCrossing for initialization faster'
        peaks  = ByHistogram(**self.kwargs)(**kwa)[0]
        return self.fromzestimate(self.data,peaks)

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

    @staticmethod
    def cfit(data,rates,params,emiter,tol,lowerbound=1e-4): # pylint: disable = too-many-arguments
        'fitting using c calls'
        out = emrunner(data,rates,params,emiter,lowerbound,tol)
        return out.rates, out.params

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
        rates, params = self.fittingalgo(self.data,rates,params,self.emiter,self.tol)
        while any(params[:,1]>self.upperbound):
            idx = np.argmax(params[:,1])
            # split the one with highest covariance
            nrates,nparams = self.splitparams(rates,params,idx)
            # could be improved by reducing the number of peaks (and associated data)
            # to optimized during emstep
            rates, params = self.fittingalgo(self.data,nrates,nparams,self.emiter,self.tol)
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
        rates, params = self.fittingalgo(self.data,rates,params,self.emiter,self.tol)
        notchecked = np.array([True]*params.shape[0])

        while any(notchecked):
            print(f"params.shape={params.shape}")
            for idx in (i for i,j in enumerate(notchecked) if j):
                nrates,nparams = self.splitparams(rates,params,idx)

                # thermalise, thermalise only the splitted peaks to save time
                nrates,nparams = self.fittingalgo(self.data,nrates,nparams,self.emiter,self.tol)
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
        self.fittingalgo = self.skfit
        super().__init__(**kwa)

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


class RandInit(ByEM):
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

        rates, params = self.__fit()
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
            rates,params = self.fittingalgo(self.data,rates,params,self.emiter,self.tol)
            score        = self.score(self.data,params)
            bic          = self.bic(score,rates,params)
            bicpeaks.append((bic,rates,params))

        return sorted(bicpeaks,key=lambda x:x[0])[0]

    def __fit(self):
        if isinstance(self.nsamples,Iterable):
            return sorted([self.nrandinit(_) for _ in self.nsamples],
                          key=lambda x: x[0])[0][-2:]

        return self.nrandinit(self.nsamples)[-2:]
