#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Use Cholesky decompositon for the computation of the loglikelihood...
stay in log until rates computation, and then avoid underflow
Currently implemented for 1D space  and 1D time
"""

import warnings

import numpy as np
from utils   import initdefaults
from .._core import emlogscore  # pylint: disable = import-error

# def lnormpdf(loc,var,pos):
#     return -0.5(pos-loc)**2/var # + cst

# def lexppdf(loc,scale,pos):
#     return -np.inf if loc>pos else (loc-pos)/scale-np.log(scale)

# # use cholesky here, when multidimensional space
# def gaussianloglikeli(data,rates,params):
#     return 0.

# def exponloglikeli(data,rates,params):
#     return 0.

class ExpectationMaximization:
    "Expectation Maximization class"
    tol    = 1e-6 # loglikelihood tolerance
    emiter = 1000
    precision = 1e-9
    floatprec = 1e-6

    @initdefaults(frozenset(locals()))
    def __init__(self,**_):
        pass

    @staticmethod
    def getlscore(data:np.ndarray,params:np.ndarray): # checked
        "log score of shape (len(params),len(data))"
        return emlogscore(data,params)

    @staticmethod
    def getlogresponsibility(lscore:np.ndarray,rates:np.ndarray): # checked post normalization
        "(unormalized) log of the responsibility matrix, lpz_x"
        return lscore+np.log(rates)

    @staticmethod
    def getrates(lresp:np.ndarray): # check small difference
        "recompute new rate values"
        warnings.warn("there is a logsumexp available in scipy and in np, check these")
        # avoids underflow using 'log-sum-exp' formula
        maxes = np.max(lresp,axis=1).reshape(-1,1)
        rates = np.exp(maxes) + np.sum(np.exp(lresp-maxes),axis=1).reshape(-1,1)
        return rates/rates.sum()

    @classmethod
    def getgaussianparams(cls,
                          data:np.ndarray,
                          resp:np.ndarray,
                          lowercov:float): # should be ok
        "returns the gaussian mixture parameters"
        means = np.dot(resp,data)
        centers = [data-means[i] for i in range(means.shape[0])]
        covs = np.array([np.cov(centers[i].T,aweights=resp[i,:]) for i in range(means.shape[0])])
        covs/=np.sum(resp,axis=1)
        # apply lower bound here
        covs[covs<lowercov]=lowercov
        return np.hstack([means,covs.reshape(-1,1)])

    @classmethod
    def getresp(cls,lresp):
        "returns (normalized) responsibility matrix"
        resp = np.exp(lresp)+cls.floatprec
        return resp/np.sum(resp,axis=0)

    @classmethod
    def gettimeparams(cls,data:np.ndarray,resp:np.ndarray): # to check
        "time related only in data"
        # duration scale
        scales = np.dot(resp,data).ravel()/np.sum(resp,axis=1)
        return np.hstack([np.zeros((resp.shape[0],1)),scales.reshape(-1,1)])

    @classmethod
    def getparamswithtime(cls,data:np.ndarray,lresp:np.ndarray,lowercov:float):
        "get params for spatial and time parameters"
        # the last data dimension is time related
        resp    = cls.getresp(lresp)
        spatial = cls.getgaussianparams(data[:,:-1].reshape(data.shape[0],-1),
                                        resp,
                                        lowercov)
        time    = cls.gettimeparams(data[:,[-1]],resp)
        return np.hstack([spatial,time])

    @classmethod
    def maximization(cls,
                     data:np.ndarray,
                     lresp:np.ndarray,
                     lowercov:float):
        """
        maximization step
        lowercov is the lower covariance value an element can take
        """
        rates  = cls.getrates(lresp)
        params = cls.getparamswithtime(data,lresp,lowercov)
        return rates, params

    # @staticmethod
    # def getllikelihood(data,rates,params):
    #     """
    #     this is the tricky bit
    #     spatial component of llikelihood can be done using Cholesky
    #     bu not the time component
    #     """
    #     return gaussianloglikeli(data,rates,params)+exponloglikeli(data,rates,params)

    @classmethod
    def oneemstep(cls,
                  data:np.ndarray,
                  rates:np.ndarray,
                  params:np.ndarray,
                  lowercov:float):
        "performs one EM step"
        # the E step
        lresp = cls.getlogresponsibility(cls.getlscore(data,params),rates)
        # the M step
        return cls.maximization(data,lresp,lowercov)

    def emsteps(self,
                data:np.ndarray,
                rates:np.ndarray,
                params:np.ndarray):
        "performs n emsteps"
        # prevllike = self.getllikelihood(data,rates,params)
        for i in range(self.emiter): # pylint:disable = unused-variable
            rates,params = self.oneemstep(data,rates,params,self.precision**2)
            # llike        = self.getllikelihood(data,rates,params)
            # if llike-prevllike<self.tol:
            #     break
        return rates,params
