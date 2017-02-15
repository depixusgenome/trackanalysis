#!/usr/bin/env python3
# -*- coding: utf-8 -*-

u'''
regroups functions and classes to assemble a sequence
'''

import sys
from itertools import combinations
import random
from copy import deepcopy
import numpy
from scipy.optimize import basinhopping,OptimizeResult
from scipy.stats import truncnorm
from sequences import OligoHit


# Fixed parameters
# bp_to_nm = 1.100
# error_in_z = 3, in nanometers
# (rounded) error_in_bp = 3

# to do :
#    * include a position in base pairs
#    * check the overlap
#    * change the steps from permutations to gaussian scale
#    * make unit tests

# to benchmark:
#    * fix size of sequences, vary size of oligos and overlap
#    * time/ number of steps for convergence (probably needs optimization)
#    * reliability with regard to short sequence repeats (AAA..., ATATA...)
#    * size of correct sequences obtained


def print_state(xstate, func, accepted): # pylint: disable=unused-argument
    u'''use this to print the state at each Monte Carlo step
    '''
    print("at minimum %.4f accepted %d" % (func, int(accepted)))

def no_minimizer(fun, xinit, *args, **options): # pylint: disable=unused-argument
    u'''use this minimizer to avoid minimization step in basinhopping
    '''
    return OptimizeResult(x=xinit, fun=fun(xinit), success=True, nfev=1)

def gen_sequence(length=1000): # move to simulation file
    u'''
    generates a sequence of defined length
    '''
    return "".join(random.choice("atcg") for i in range(length))

class HoppingSteps:
    u'''
    Class to define boundaries, steps for basinhopping
    Can forbid flipping of peaks within the same batch
    '''
    def __init__(self,**kwargs):
        self.min_bpos = kwargs.get("min_bpos",0) # in number of bases
        self.max_bpos = kwargs.get("max_bpos",sys.maxsize) # in number of bases
        self.scale = kwargs.get("scale",1) # in number of bases
    def __call__(self,xstate):
        pass

def rtruncnorm_step(obj:HoppingSteps,xstate):
    u'''
    rounded and truncated normal step
    '''
    assert isinstance(obj,HoppingSteps)
    xstate = numpy.round([truncnorm.rvs(a=(obj.min_bpos-i)/obj.scale,
                                        b=(obj.max_bpos-i)/obj.scale,
                                        loc=i,
                                        scale=obj.scale) for i in xstate])
    return xstate

def flip_step(obj:HoppingSteps,xstate):
    u'''
    flips the position of two xstate values
    '''
    assert isinstance(obj,HoppingSteps)
    idx = numpy.random.randint(0,len(xstate)-1)
    xstate[idx],xstate[idx+1]=xstate[idx+1],xstate[idx]
    return xstate

class OligoWrap:
    u'''
    decorator for use of bpos array instead of list of OligoHit
    '''
    def __init__(self,oligos):
        self.oligos=oligos

    def __call__(self,func):
        u'''returns a function which takes new positions of oligos
        instead of new oligos
        required for basinhopping
        '''
        def wrapped_func(bpos):
            u'''
            wrapper
            '''
            oligos=oligos_from_bpos(self.oligos,bpos)
            return func(oligos)
        return wrapped_func


def oligos_from_bpos(olis,bpos):
    u'''
    returns a function which takes an array of pos instead of oligos
    '''
    assert len(olis)==len(bpos)
    oligos = [deepcopy(i) for i in olis]
    for idx,val in enumerate(bpos):
        oligos[idx].bpos=val
    return oligos

def noverlap_bpos_energy(oligos): # to optimize
    u'''use noverlap_bpos to compute energy
    '''
    energy=0
    for it1,it2 in combinations(oligos,2):
        energy-=OligoHit.noverlap_bpos(it1,it2)**2

    return energy

def tail_overlap_energy(oligos)->float: # ok-ish
    u'''
    sort by bpos and apply tail_overlap
    '''
    oligo_sort = sorted(oligos,key=lambda x :x.bpos)
    overlaps = numpy.array([len(OligoHit.tail_overlap(oli.seq,oligo_sort[idx+1].seq))\
                        for idx,oli in enumerate(oligo_sort[:-1])])
    return -sum(overlaps[overlaps!=numpy.array(None)]**2)

def acceptance(): # to implement
    u'''
    provides arg for accept_test
    complements MH-acceptance ratio
    can return "force accept" to escape local minima
    '''
    # if there is a switch of two peaks within the same batch return False
    return True

def fit_oligos(oligos,energy_func,**kwargs):
    u'''
    python version of assemble_oligos_idle_action
    '''
    xstate0 = numpy.array([i.pos for i in oligos])
    hopp = basinhopping(energy_func,xstate0,**kwargs)
    return hopp
