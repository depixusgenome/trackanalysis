#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Creates a histogram from available events"
import itertools
from functools        import partial
from typing           import Dict, Tuple
import numpy as np

from utils            import initdefaults

from .._core          import empz_x, emrunner, emscore  # pylint: disable = import-error
from .histogramfitter import ByHistogram  # pylint: disable = unused-import
# create abstract class with different fitting algorithms

class EMFlagger:
    'flag peak corresponding to events'
    mincount=5
    @initdefaults(frozenset(locals()))
    def __init__(self,**_):
        pass

    def __strip(self, params, events):
        '''
        then assigns events to most likely peaks
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

class ByEM(EMFlagger):# needs cleaning
    '''
    finds peaks and groups events using Expectation Maximization
    the number of components is estimated using BIC criteria
    '''
    emiter     = 1000
    tol        = 0.5  # loglikelihood tolerance
    decimals   = 4    # rounding values
    floaterr   = 1e-10
    minpeaks   = 1
    upperbound = 0.005**2 # in microns**2

    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        super().__init__(**_)

    def __call__(self,**kwa):
        return self.find(**kwa)

    def _findpeaks(self,data):
        rates,params = self.initialize(data,maxbins=1)
        return self.splitter(data,rates,params,upperbound=self.upperbound)[-2:]

    def findfromzestimates(self,**kwa):
        "estimates starting parameters using kernel density"
        rates, params = self.kernelinitializer(**kwa)
        events = kwa.get("events",None)
        data   = np.array([[np.nanmean(evt),len(evt)]
                           for cycle in events
                           for evt in cycle])
        return self.splitter(data,rates,params,upperbound=self.upperbound)[-2:]

    def find(self, **kwa):
        """
        find peaks along z axis
        keyword arguments are :
        hist,
        events,
        pos,
        precision, hf sigma
        """
        rates, params = self.findfromzestimates(**kwa) # after
        events        = kwa.get("events",None)
        data          = np.array([[np.nanmean(evt),len(evt)]
                                  for cycle in events
                                  for evt in cycle])
        #rates,params = self._findpeaks(data) # before
        peaks, ids    = self.group(rates.ravel()*data.shape[0],params,events)
        _, bias,slope = kwa.get("hist",(np.array([]),0,1))
        return peaks * slope + bias , ids

    def __fromzestimate(self,data:np.ndarray,zpeaks:np.ndarray):
        'estimates other params values from first estimates in z postion'
        # group peaks too close
        window = 0.005 # to change

        tomerge = np.where(np.diff(zpeaks)>window)[0]
        bins    = [zpeaks[0]-0.1]+[np.mean(zpeaks[i:i+2]) for i in tomerge]+[zpeaks[-1]+0.1]

        # estimate rates, params using merged
        params = self.paramsfromzbins(data,bins,mincount=0)
        return np.ones(params.shape[0]).reshape(-1,1)/params.shape[0], params

    def paramsfromzbins(self,data,bins,mincount=None):
        "given a list of bins along z axis, estimates the parameters"
        mincount  = self.mincount if mincount is None else mincount
        digi      = np.digitize(data[:,:-1].ravel(),bins)
        clas      = {idx:np.array([data[_1] for _1,_2 in enumerate(digi) if _2==idx])
                     for idx in set(digi)}
        params = np.vstack([list(itertools.chain.from_iterable(zip(np.nanmean(clas[idx],axis=0),
                                                                   np.nanvar(clas[idx],axis=0))))
                            for idx in set(digi)
                            if len(clas[idx])>self.mincount])
        params[:,-2] = 0.
        params[:,-1] = [np.nanstd(clas[idx][-1])
                        for idx in set(digi)
                        if len(clas[idx])>self.mincount]
        return params

    def initialize(self,data:np.ndarray,maxbins:int=1):
        'initialize using density'
        bins       = np.histogram(data[:,0],bins=maxbins)[1]
        bins[-1]  += 0.1
        params     = self.paramsfromzbins(data,bins)
        return 1/len(params)*np.ones((len(params),1)), params

    def kernelinitializer(self,**kwa):
        'uses ZeroCrossing for initialization (much faster)'
        estimates = ByHistogram()(**kwa)[0]
        estimates.sort() # should already be sorted
        events    = kwa.get("events",None)
        # can merge close zpeaks from later subdivision by EM
        data = np.array([[np.nanmean(evt),len(evt)]
                         for cycle in events
                         for evt in cycle])
        return self.__fromzestimate(data,estimates)

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
    def cfit(data,rates,params,emiter,bounds=(10**2,0.001**2)):
        'fitting using c calls'
        out = emrunner(data,rates,params,emiter,bounds[0],bounds[1])
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

    def splitter(self,data,rates,params,upperbound=0.005**2):
        'splits the peaks with great Z variance'
        delta = np.array([0.001]*params.shape[1]) # in microns
        delta[-2:] = 0.0
        delta[range(1,2,len(delta))] = 0.0 # no delta in cov
        score, rates, params = self.cfit(data,rates,params,self.emiter)
        # if the number of events in rates is too low, skip this
        # while np.logical_and(any(params[:,1]>upperbound),
        # rates.ravel()*data.shape[0]>self.mincount):
        while any(params[:,1]>upperbound):
            idx = np.argmax(params[:,1])
            # split the one with highest covariance
            nparams         = np.vstack([params[:idx+1],params[idx:]])
            nparams[idx]   -= delta
            nparams[idx+1] += delta
            nrates = np.vstack([rates[:idx+1],rates[idx:]])
            nrates[idx:idx+2] /=2
            # could be improved by reducing the number of peaks (and associated data)
            # to optimized during emstep
            score, rates, params = self.cfit(data,nrates,nparams,self.emiter)
        return score,rates,params

class ByEmMutu(ByEM):
    ''' uses mutual information theory to decide whether peaks should be splitted or not'''

    @staticmethod
    def mutualinformation(score:np.ndarray,
                          rates:np.ndarray):
        '''
        computes the mutual information of the peaks
        if element i,j has >0 then  i,j are dependent (i.e. represents the same data)
        '''
        pz_x = empz_x(score,rates)
        pij  = np.array(np.matrix(pz_x)*np.matrix(pz_x).T)/pz_x.shape[1]
        return pij*np.log2( (pij/np.mean(pz_x,axis=1)).T/np.mean(pz_x,axis=1) )

    def isbetter(self,score:np.ndarray,rates:np.ndarray)->bool:
        '''
        defines condition on mutualinformation
        returns True if peaks are better split,
        False otherwise
        '''
        info    = self.mutualinformation(score,rates)
        # eps     = max(abs(np.diag(info)))
        offdiag = np.array([info[i] for i in zip(*np.triu_indices_from(info,k=1))])
        # if any(offdiag>-eps):
        #     return False
        if any(offdiag>0):
            return False
        return True

    def mutualsplit(self,data,rates,params):
        '''
        splits the peaks with great Z variance
        if mutual information allows keep the split of peaks
        '''
        delta                        = np.array([0.001]*params.shape[1]) # in microns
        delta[-2:]                   = 0.0
        delta[range(1,2,len(delta))] = 0.0 # no delta in cov
        score, rates, params         = self.cfit(data,rates,params,self.emiter)
        notchecked = np.array([True]*params.shape[0])

        while any(notchecked):
            print(f'notchecked={notchecked, np.sum(notchecked)}')
            asort = np.argsort(params[:,1]) # cov along Z
            params=params[asort]
            for idx in (i for i,j in enumerate(notchecked) if j):
                # split
                nparams             = np.vstack([params[:idx+1],params[idx:]])
                nparams[idx]       -= delta
                nparams[idx+1]     += delta
                nrates              = np.vstack([rates[:idx+1],rates[idx:]])
                nrates[idx:idx+2]  /= 2
                # thermalise
                sco,rat,par = self.cfit(data,nrates, nparams, self.emiter)
                # check mutual information
                if self.isbetter(sco,rat):
                    notchecked   = np.insert(notchecked,idx,True)
                    rates,params = rat,par
                    break
                notchecked[idx]=False

        return score,rates,params

    def _findpeaks(self,data):
        rates,params = self.initialize(data,maxbins=1)
        return self.mutualsplit(data,rates,params)[-2:]


    # the longest steps are done by finding the number of peaks
    # -> solution run ByHist() and find the peaks
    # regroup the closest ones (those in  a window of 5nm) then apply ByEM
