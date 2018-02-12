#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Creates a histogram from available events"

import itertools
from enum import Enum
from functools import partial
from typing import Callable, Dict, Optional, Tuple

import numpy as np

from utils import initdefaults
from utils.logconfig import getLogger
from .._core import exppdf, normpdf, emrunner # pylint: disable=import-error
from .histogramfitter import ByHistogram # pylint: disable=unused-import

LOGS = getLogger(__name__)

class COVTYPE(Enum):
    'defines constraints on covariance'
    ANY  = "any"
    TIED = "tied"


class ByEM: # pylint: disable=too-many-public-methods
    '''
    finds peaks and groups events using Expectation Maximization
    the number of components is estimated using BIC criteria
    '''
    emiter   = 100
    mincount = 5
    tol      = 0.5  # loglikelihood tolerance
    decimals = 4    # rounding values
    covtype  = COVTYPE.TIED
    deltabic = 1    # significant increase in bic
    floaterr = 1e-10
    params  : np.ndarray
    rates   : np.ndarray
    minpeaks  = 1
    spaceonly = False
    covmap : Callable = np.vectorize(lambda x : float(x)) # pylint:disable=unnecessary-lambda
    kwa : Dict = {}

    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        pass

    def __call__(self,**kwa):
        _, bias, slope = kwa.get("hist",(0,0,1))
        self.kwa = kwa
        return self.find(kwa.get("events",None), bias, slope, kwa["precision"])

    def find(self, events, bias, slope, precision=None):
        'find peaks along z axis'
        data       = np.array([[np.nanmean(evt),len(evt)]
                               for cycle in events
                               for evt in cycle])
        maxpeaks   = int((max(data[:,0])-min(data[:,0]))//precision)
        search     = self.fullsearch(data,maxpeaks)
        params     = search[-1]
        asort      = np.argsort(params[:,0,0])
        peaks, ids = self.__strip(params[asort],events)
        return peaks * slope + bias , ids

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

    # to test
    def nparams(self,params):
        'returns the number of estimated params'
        if self.covtype is COVTYPE.TIED:
            dim = params.shape[1]//2-1
            return params.size-dim*(params.shape[0]-1)
        return params.size

    def initialize(self,data:np.ndarray,maxbins:int=1)->np.ndarray:
        'initialize using density'
        bins      = np.histogram(data[:,0],bins=maxbins)[1]
        bins[-1] += 0.1
        digi      = np.digitize(data[:,:-1].ravel(),bins)
        clas      = {idx:np.array([data[_1] for _1,_2 in enumerate(digi) if _2==idx])
                     for idx in set(digi)}
        params    = np.array([[(np.nanmean(clas[idx][:,:-1],axis=0),
                                np.cov(clas[idx][:,:-1].T) # to correct
                                if len(clas[idx])>self.mincount else 0),
                               (0,np.nanstd(clas[idx][:,-1]))] for idx in set(digi)])
        params[:,0,1][params[:,0,1]==0]=np.mean(params[:,0,1],axis=0)
        params[:,1,1][params[:,1,1]==0]=np.mean(params[:,1,1],axis=0)
        params[:,0,1] = self.covmap(params[:,0,1])
        return 1/len(params)*np.ones((len(params),1)) , params

    @classmethod
    def pdf(cls,*args):
        '''
        args : np.array([[xloc,xscale,xpos],
                         [yloc,yscale,ypos],
                         [zloc,zscale,zpos],
                         [tloc,tscale,tpos]])
        '''
        param, datum = args[0]
        return cls.spatialpdf(*param[0],datum[:-1])*exppdf(*param[1],datum[-1])

    @staticmethod
    def mvnormpdf(mean,cov,pos):
        'multivariate normal'
        cent = pos-mean
        num  = np.dot(np.dot(cent,np.linalg.inv(cov)),cent.T)
        return np.exp(-0.5*num)/np.sqrt(float(np.linalg.det(cov)))

    # pytest
    @classmethod
    def spatialpdf(cls,mean,cov,pos):
        'proportional to normal pdf of multivariate distribution'
        if len(pos)==1:
            return float(normpdf(float(mean), float(cov), float(pos)))
        return cls.mvnormpdf(mean,cov,pos)

    def score(self,data:np.ndarray,params)->np.ndarray:
        'return the score[i,j] array corresponding to pdf(Xj|Zi, theta)'
        # use bin n data to reduce computation
        score = np.ones((len(params),data.shape[0]))*10*self.floaterr
        pairs = [(row,col)
                 for row,i in enumerate(params[:,0])
                 for col in np.argwhere((data[:,0]-i[0])**2<100*i[1]).ravel()]
        for row,col in pairs:
            score[row,col]+=self.pdf((params[row],data[col]))
        return score

    def emstep(self,data:np.ndarray,rates:np.ndarray,params:np.ndarray):
        'Expectation then Maximization steps of EM'
        score = self.score(data,params)
        pz_x  = score*rates # P(Z,X|theta) prop P(Z|X,theta)
        pz_x  = np.array(pz_x)/np.sum(pz_x,axis=0) # renorm over Z
        rates, params = self.maximization(pz_x,data)
        return self.score(data,params), rates, params

    def __maximizeparam(self,data,proba):
        'maximizes a parameter'
        nmeans = np.array(np.matrix(proba)*data[:,:-1]).ravel()
        return
        # ncov   = np.cov(data[:,:-1].T,aweights = proba ,ddof=0) # WRONG: need to center
        # tscale = np.sum(proba*data[:,-1])
        # return [(nmeans,self.covmap(ncov)),(0.,tscale)]

    # to pytest
    def maximization(self,pz_x:np.ndarray,data:np.ndarray):
        'returns the next set of parameters'
        npz_x = pz_x/np.sum(pz_x,axis=1).reshape(-1,1)

        nrates   = np.mean(pz_x,axis=1).reshape(-1,1)
        maximize = partial(self.__maximizeparam,data)
        params   = np.array(list(map(maximize,npz_x))) # type: ignore
        if self.covtype is COVTYPE.TIED:
            meancov       = np.mean(params[:,0,1],axis=0)
            params[:,0,1] = meancov
        return nrates, params

    # pytest
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
        # number of params rates + params assuming tmean is 0
        return -2*llikeli + self.nparams(params) *np.log(0.5*score.shape[1]/np.pi)

    def aic(self,score:np.ndarray,rates:np.ndarray,params:np.ndarray)->float:
        'returns aic value'
        return 2*self.nparams(params) -2*self.llikelihood(score,rates)

    @classmethod
    def llikelihood(cls,score:np.ndarray,rates:np.ndarray)->float:
        'returns loglikelihood'
        return np.sum(np.log(np.sum(rates*score,axis=0)))

    # to pytest
    def fit(self,data,rates,params,prevll:Optional[float] = None):
        'fit a given set of params'
        prevll = self.llikelihood(self.score(data,params),rates) if prevll is None else prevll
        for _ in range(self.emiter):
            score,rates,params = self.emstep(data,rates,params)
            llikeli            = self.llikelihood(score,rates)
            if abs(llikeli-prevll) < self.tol:
                break
            prevll = llikeli
        return score, rates, params

    def cfit(self,data,rates,params,bounds=(0.004**2,0.001**2)):
        'fitting using c calls'
        tofloat   = np.vectorize(float)
        paramsmat = np.vstack(tofloat(params)).reshape(-1,4)
        out       = emrunner(data,rates,paramsmat,self.emiter,bounds[0],bounds[1])
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

    def checkparam(self,data,params,bounds):
        '''
        checks whether the addition of a new peak is worth
        '''
        nrates = np.ones((len(params),1))/len(params)

        nfit = self.cfit(data,nrates,params,bounds)
        print("nfit={nfit}")
        return self.bic(*nfit),nfit[-1]

    # def frompeakstoparams():
    #     pass

    def addpeaks(self,data,rates,params,bounds=(0.005**2,0.001**2)):
        '''
        iteratively splits each peaks in 2 until adding more peaks does not improve the bic
        '''
        visited = set([])
        delta = np.array([0.005]*params.shape[1],dtype="f4") # in microns
        delta[-2:] = 0.0

        score, rates, params = self.cfit(data,rates,params,bounds)
        bic1 = self.bic(score,rates,params)

        while True:
            for idx in range(len(params)):
                nparams         = np.vstack([params[:idx+1],params[idx:]])
                nparams[idx]   -= delta
                nparams[idx+1] += delta
                bic2, nparams   = self.checkparam(data,nparams,bounds)
                visited.update({idx})
                if bic2<bic1:
                    params  = np.array(nparams,copy=True)
                    bic1    = bic2
                    visited.remove(idx)
                    visited = set(i+1 if i>idx else i for i in visited)

            if len(visited)==params.shape[0]:
                break

        return params

    def fullrecord(self,data:np.ndarray,maxpeaks:int):
        '''
        for debugging purposes
        '''
        results = []
        rates,params       = self.initialize(data,maxpeaks)
        score,rates,params = self.fit(data,rates,params,prevll=None)
        results.append((score,rates,params))
        # remove peaks that are too close after fitting, and update
        # keep               = self.__rmduplicates(params,rates)
        # score,rates,params = self.emstep(data,rates[keep],params[keep])
        score,rates,params = self.emstep(data,rates,params)

        #assign = np.array(list(map(len,self.assign(score).values())))
        while len(rates)>self.minpeaks:
            asort              = rates.ravel().argsort()
            score,rates,params = self.fit(data,rates[asort][1:],params[asort][1:],prevll=None)
            # keep               = self.__rmduplicates(params,rates)
            # score,rates,params = self.emstep(data,rates,params)
            results.append((score,rates,params))
            #assign             = np.array(list(map(len,self.assign(score).values())))
        return results

    def fullcrecord(self,data:np.ndarray,maxpeaks:int,bounds=(0.005**2,0.001**2)):
        '''
        for debugging purposes
        '''
        results = []
        rates,params       = self.initialize(data,maxpeaks)
        score,rates,params = self.cfit(data,rates,params,bounds)
        results.append((score,rates,params))
        # remove peaks that are too close after fitting, and update
        # keep               = self.__rmduplicates(params,rates)
        # score,rates,params = self.emstep(data,rates[keep],params[keep])

        #assign = np.array(list(map(len,self.assign(score).values())))
        while len(rates)>self.minpeaks:
            asort              = rates.ravel().argsort()
            score,rates,params = self.cfit(data,rates[asort][1:],params[asort][1:],bounds)
            # keep               = self.__rmduplicates(params,rates)
            # score,rates,params = self.emstep(data,rates,params)
            results.append((score,rates,params))
            #assign             = np.array(list(map(len,self.assign(score).values())))
        return results

    def fullsearch(self,data,maxpeaks:int):
        '''
        returns the parameters corresponding to minimal bic,
        not first local minimum
        '''
        rates,params       = self.initialize(data,maxpeaks)
        score,rates,params = self.fit(data,rates,params,prevll=None)
        result             = score,rates,params

        assign = np.array(list(map(len,self.assign(score).values())))
        bic    = None
        while any(assign<self.mincount) or len(rates)>self.minpeaks:
            minbic             = bic
            asort              = rates.ravel().argsort()
            score,rates,params = self.fit(data,rates[asort][1:],params[asort][1:],prevll=None)
            assign             = np.array(list(map(len,self.assign(score).values())))
            if not any(assign<self.mincount):
                bic    = self.bic(score,rates,params)
                minbic = bic if minbic is None else minbic
                if bic<=minbic:
                    minbic = bic
                    result = score,rates,params
        return result

    def fitdata(self,data:np.ndarray,maxpeaks:int):
        '''
        calls initialization with maximal number of peaks
        runs fits until convergence
        remove peaks assigned to less than mincount
        then removes the least likely peak, converge
        and repeats
        '''
        rates,params       = self.initialize(data,maxpeaks)
        score,rates,params = self.fit(data,rates,params,prevll=None)

        assign = np.array(list(map(len,self.assign(score).values())))
        bic    = None
        while any(assign<self.mincount) or len(rates)>self.minpeaks:
            prevbic            = bic
            prev               = score,rates,params
            asort              = rates.ravel().argsort()
            score,rates,params = self.fit(data,rates[asort][1:],params[asort][1:],prevll=None)
            assign             = np.array(list(map(len,self.assign(score).values())))
            if not any(assign<self.mincount):
                bic      = self.bic(score,rates,params)
                finished = False if prevbic is None else bic-prevbic>self.deltabic
                if finished :
                    return prev
        return score,rates,params
