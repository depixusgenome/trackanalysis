#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'numba compiled functions'


from numba.pycc import CC
import numpy as np

cc=CC("aotutils")

cc.verbose=True

PI=3.14159

@cc.export("normpdf","f4(f4,f4,f4)")
def normpdf(loc,var,pos):
    'normal pdf'
    return np.exp(-0.5*((pos-loc)**2/var))/(np.sqrt(2*PI*var))

@cc.export("exppdf","f4(f4,f4,f4)")
def exppdf(loc, scale, pos):
    'pdf of exponential dist'
    return 0 if loc>pos else float(np.exp((loc-pos)/scale)/scale)

# @cc.export("mvnormpdf","f4(f4[:],f4[:,:],f4[:])")
# def mvnormpdf(mean,cov,pos):
#     'proportional to normal pdf of multivariate distribution'
#     #cent = np.matrix(pos-mean,dtype='f4')
#     return np.exp(-0.5*float(np.matrix(pos-mean)*np.linalg.inv(cov)*np.matrix(pos-mean).T))/\
#         np.sqrt(float(np.linalg.det(cov)))

if __name__=="__main__":
    cc.compile()
    pass
