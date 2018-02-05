#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Creates a histogram from available events"
from typing import (Dict, Iterable, Union, cast)

import numpy as np
from sklearn.mixture import GaussianMixture

from utils import initdefaults
from utils.logconfig import getLogger

from .histogramfitter import ZeroCrossingPeakFinder

LOGS       = getLogger(__name__)

HistInputs = Union[Iterable[Iterable[float]],
                   Iterable[Iterable[np.ndarray]],
                   Iterable[float]]
BiasType   = Union[None, float, np.ndarray]

class ByGaussianMix:
    '''
    finds peaks and groups events using Gaussian mixture
    the number of components is estimated using BIC criteria
    '''
    max_iter        = 10000
    cov_type        = 'full'
    peakwidth       = 1
    crit            = 'bic'
    mincount        = 5
    varcmpnts       = 0.2

    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        pass

    def __call__(self,**kwa):
        pos               = kwa.get("pos",None)
        self.peakwidth    = kwa.get("precision",1)
        hist, bias, slope = kwa.get("hist",(0,0,1))
        return self.find(pos, hist, bias, slope)

    # needs cleaning
    def find(self,pos: np.ndarray, hist, bias:float = 0., slope:float = 1.):
        'find peaks'
        events   = np.hstack(pos)
        zcnpeaks = len(ZeroCrossingPeakFinder()(hist,bias, slope))
        kwargs   = {'covariance_type': self.cov_type,
                    'max_iter' : self.max_iter}
        # needs better estimation
        gmm      = self.__fit(events.reshape(-1,1),
                              max(int(zcnpeaks*(1+self.varcmpnts)),2),
                              max(int(zcnpeaks*(1-self.varcmpnts)),1),
                              kwargs)

        peaks    = gmm.means_.reshape(1,-1)[0] * slope + bias
        ids      = self.__strip(pos,events.reshape(-1,1),gmm)

        speaks   = sorted([(idx,val) for idx,val in enumerate(peaks)],
                          key =lambda x:x[1])

        sort     = {idy[0] :idx for idx,idy in enumerate(speaks)}
        sort[cast(int,np.iinfo("i4").max)] = cast(int,np.iinfo("i4").max)
        def sorting(idarr):
            'rename indices to match sorted peaks'
            if idarr.size>0:
                return np.array([sort[_] for _ in idarr])
            return np.array([])
        return np.sort(peaks), [sorting(idx) for idx in ids]

    def __strip(self,pos,evts,gmm):
        'removes peaks which have fewer than mincount events'
        predicts = gmm.predict(evts)
        keep     = [pkid for pkid in range(gmm.n_components) if sum(predicts==pkid)>=self.mincount]

        def assign(zpos):
            'set id'
            idx = gmm.predict(zpos)[0]
            return idx if idx in keep else np.iinfo("i4").max

        vids = np.vectorize(assign)
        return np.array([vids(zpos) if zpos.size>0 else np.array([]) for zpos in pos])

    def __fit(self,evts,maxcmpts,mincmpts,kwargs):
        '''
        runs Gaussian Mixture for different components
        returns the one which minimizes crit
        '''
        gmms = self.__run_gmms(evts,maxcmpts,mincmpts,kwargs)
        return self.__min_crit(self.crit,evts,gmms)

    @staticmethod
    def __run_gmms(evts:np.ndarray,maxncmps:int,mincmps:int,kwargs:Dict):
        gmms = [GaussianMixture(n_components = ite,**kwargs) for ite in range(mincmps,maxncmps)]
        for ite in range(maxncmps-mincmps):
            gmms[ite].fit(evts)
        return gmms

    @staticmethod
    def __min_crit(crit:str,evts:np.ndarray,gmms):
        values = [getattr(gmm,crit)(evts) for gmm in gmms]
        return gmms[np.argmin(values)]
