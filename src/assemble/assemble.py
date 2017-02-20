#!/usr/bin/env python3
# -*- coding: utf-8 -*-

u'''
regroups functions and classes to assemble a sequence
'''

import sys
from itertools import combinations
from copy import deepcopy
from typing import Callable # pylint: disable=unused-import
import numpy
from scipy.optimize import basinhopping,OptimizeResult
from scipy.stats import truncnorm
from utils import initdefaults
from . import oligohit

# Fixed parameters
# bp_to_nm = 1.100
# error_in_z = 3, in nanometers
# (rounded) error_in_bp = 3

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

class HoppingSteps:
    u'''
    Class to define boundaries, steps for basinhopping
    Can forbid flipping of peaks within the same batch
    '''
    def __init__(self,**kwargs):
        self.min_x = kwargs.get("min_x",0) # in number of bases
        self.max_x = kwargs.get("max_x",sys.maxsize) # in number of bases
        self.scale = kwargs.get("scale",1) # in number of bases
        self.rvs = kwargs.get("rvs",[]) # list of distributions

    def __call__(self,xstate): # should be overriden
        pass



class PreFixedSteps(HoppingSteps):
    u'''
    calls predefined fixed distributions
    '''
    def __call__(self,*args):
        return call_rvs(self,*args)

def call_rvs(obj:HoppingSteps,*args): # pylint: disable=unused-argument
    u'''
    call predefined distributions
    '''
    return numpy.array([i() for i in obj.rvs])

def rtruncnorm_step(obj:HoppingSteps,xstate):
    u'''
    rounded and truncated normal step
    '''
    assert isinstance(obj,HoppingSteps)
    xstate = numpy.round([truncnorm.rvs(a=(obj.min_x-i)/obj.scale,
                                        b=(obj.max_x-i)/obj.scale,
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
    decorator for use of bpos array instead of list of oligohit
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
        oligos[idx].bpos=numpy.round(val)
    return oligos

def noverlaps_energy(oligos):
    u'''use noverlap_bpos to compute energy
    '''
    energy=0
    for ol1,ol2 in combinations(oligos,2):
        energy-=ol1.noverlaps(ol2)**2

    return energy

def tail_overlap_energy(oligos)->float:
    u'''
    sort by bpos and apply tail_overlap
    '''
    oligo_sort = sorted(oligos,key=lambda x :x.bpos)
    overlaps = numpy.array([len(oligohit.tail_overlap(oli.seq,oligo_sort[idx+1].seq))\
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


class MCAssemble():
    u'''Monte Carlo for assembling sequences from oligohits
    '''
    callback = None # type: Callable
    minimizer = no_minimizer # type: Callable
    state_init = None # type: numpy.ndarray
    state = None # type: numpy.ndarray
    func = None # type: Callable[[numpy.ndarray],float]
    acceptance = None # type: Callable
    niter = 1000
    result = None
    step = HoppingSteps()

    @initdefaults
    def __init__(self,**_):
        pass

    def run_nsteps(self,nsteps:int,**_)->None:
        u'''runs a specified number of steps
        '''
        if self.state is None:
            self.state=self.state_init
        self.result = basinhopping(self.func,
                                   self.state,
                                   take_step=self.step,
                                   accept_test=self.acceptance,
                                   minimizer_kwargs=dict(method=self.minimizer),
                                   callback=self.callback,
                                   niter=nsteps,
                                   **_)
        self.update(self.result)

    def run(self):
        u'runs niter steps'
        self.run_nsteps(self.niter)

    def update(self,result:OptimizeResult):
        u'''
        update the simulator from result
        '''
        self.state = result.x
