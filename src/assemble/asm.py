#!/usr/bin/env python3
# -*- coding: utf-8 -*-

u'''
regroups functions and classes to initialise assemblers
'''

import sys
from typing import Callable, Iterable # pylint: disable=unused-import
import copy
from multiprocessing import Pool
import numpy
from scipy.optimize import basinhopping,OptimizeResult
from scipy.stats import truncnorm

# needs fixing : each object should be pickable
#                test NestedAsmrs

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
        self.dists = kwargs.get("dists",[]) # list of distributions
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
    return numpy.array([i.rvs() for i in obj.dists])

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

class Assembler:
    u'''
    parent class for assemblers
    '''
    def __init__(self,**kwargs):
        self.state_init = kwargs.get("state_init",None) # type: numpy.ndarray
        self.state = kwargs.get("state",None) # type: numpy.ndarray
        self.func = kwargs.get("func",None) # type: Callable[[numpy.ndarray],float]
        seed = kwargs.get("seed",None)
        if seed is None:
            self.npstate = numpy.random.get_state()
        else:
            self.npstate = numpy.random.RandomState(seed).get_state()

    def run(self,*args,**kwargs):
        u'runs the assembler'
        pass

class NestedAsmrs:
    u'''
    nested Monte Carlo running different random seeds in parallel
    should update the temperature based on each asmrs
    '''
    def __init__(self,**kwargs):
        u'''
        duplicate an Assembler object for different seeds value
        '''
        self.asmr_init = kwargs.get("asmr_init",None) # Assembler
        nprocs = kwargs.get("nprocs",1) # type: int
        self.seeds = kwargs.get("seeds",[]) # type: Iterable[int]
        self.asmrs = [copy.deepcopy(self.asmr_init) for i in self.seeds]
        for idx,val in enumerate(self.seeds):
            self.asmrs[idx].npstate = numpy.random.RandomState(val).get_state()
        try:
            self._pool = Pool(processes=nprocs)
        except OSError:
            print("could not create Pool")
            self._pool = None


    def run(self,niter:int=1):
        u'run in parallel each asmrs'
        if self._pool is None:
            for asm in self.asmrs:
                asm.run(niter=niter)
        else:
            self.asmrs = self._pool.map(_run_asm,
                                        [(asm,niter) for asm in self.asmrs])


    def set_asmr_inits(self,inits):
        u'''
        sets the state_init of each of the asmrs
        '''
        for idx,init in enumerate(inits):
            self.asmrs[idx].state_init = init


    def result(self):
        u'''needs to return a result to use Recorder
        is it really needed?'''
        pass

def _run_asm(*args):
    asmr=args[0][0]
    asmr.run(niter=args[0][1])
    return asmr

class MCAssembler(Assembler):
    u'''Monte Carlo for assembling sequences from oligohits
    '''

    def __init__(self,**kwargs):
        super().__init__(**kwargs)
        self.callback = kwargs.get("callback",None) # type: Callable
        self.minimizer = kwargs.get("minimizer",no_minimizer) # type: Callable
        self.acceptance = kwargs.get("acceptance",None) # type: Callable
        self.result = OptimizeResult()
        self.step = kwargs.get("step",HoppingSteps())

    def run(self,*args,**kwargs)->None: # pylint:disable = unused-argument
        u'''runs a specified number of steps
        '''
        if not "niter" in kwargs.keys():
            kwargs["niter"]=1
        numpy.random.set_state(self.npstate)

        if self.state is None:
            self.state=self.state_init

        count = self.result.it if hasattr(self.result,"it") else 0
        self.result = basinhopping(self.func,
                                   self.state,
                                   take_step=self.step,
                                   accept_test=self.acceptance,
                                   minimizer_kwargs=dict(method=self.minimizer),
                                   callback=self.callback,
                                   **kwargs)
        self.result.it = count+kwargs.get("niter")
        self.npstate = numpy.random.get_state()
        self._update(self.result)

    def _update(self,result:OptimizeResult):
        u'''
        update the simulator from result
        '''
        self.state = result.x

def acceptance(): # could implement
    u'''
    provides arg for accept_test
    complements MH-acceptance ratio
    can return "force accept" to escape local minima
    '''
    # if there is a switch of two peaks within the same batch return False
    return True
