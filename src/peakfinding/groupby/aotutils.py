#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'collection of slow functions compiled ahead of time'


from numba.pycc import CC
import numpy as np

NBCC=CC("aotutils")

NBCC.verbose=True

PI=3.14159

@NBCC.export("normpdf","f4(f4,f4,f4)")
def normpdf(loc,var,pos):
    'normal pdf'
    return np.exp(-0.5*((pos-loc)**2/var))/(np.sqrt(2*PI*var))

@NBCC.export("exppdf","f4(f4,f4,f4)")
def exppdf(loc, scale, pos):
    'pdf of exponential dist'
    return 0 if loc>pos else float(np.exp((loc-pos)/scale)/scale)


# np.sum not supported yet?
# @NBCC.export("llikelihood","f4(f4[:,:],f4[:,:])")
# def llikelihood(score,rates):
#     'returns loglikelihood'
#     return np.sum(np.log(np.sum(rates*score,axis=0)))

# returns singular to machine precision
# @NBCC.export("mvnormpdf","f4(f4[:],f4[:,:],f4[:])")
# def mvnormpdf(mean,cov,pos):
#     'multivariate normal'
#     cent = pos-mean
#     num  = np.dot(np.dot(cent,np.linalg.inv(cov)),cent.T)
#     return np.exp(-0.5*num)/np.sqrt(float(np.linalg.det(cov)))

if __name__=="__main__":
    NBCC.compile()
