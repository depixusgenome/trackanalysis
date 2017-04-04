#!/usr/bin/env python3
# -*- coding: utf-8 -*-

u'''
regroups functions and classes to initialise assemblers
'''

import sys
from typing import Callable, Iterable # pylint: disable=unused-import
from multiprocessing import Pool
import itertools
import numpy
from scipy.optimize import basinhopping,OptimizeResult
from . import _utils as utils

# number of combinations for 4-mers and 5 nm exp precision leads to
# 4.064499031853928e+26 possibilities with 100 possibilities  that's ~4*1e19 days.
# for 1nm exp precision it falls down to 25936
# proposed solution reconstruct the sequence a batch at a time.

# reconstruction a batch at a time
# if we consider an oligo-batch at a time, then:
#     * permutation can only decrease score
#     * adding a new batch, permutation can only occur between different batches

# to add variability in (stretching,bias) for each batch (to estimate from hybridstat analyses)


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
        self.min_x = kwargs.get("min_x",0)
        self.max_x = kwargs.get("max_x",sys.maxsize)
        self.scale = kwargs.get("scale",1)
        self.dists = kwargs.get("dists",[]) # list of distributions
        self.random_state = kwargs.get("random_state",None)
    def __call__(self,xstate): # should be overriden
        pass

class PreFixedSteps(HoppingSteps):
    u'''
    calls predefined fixed distributions
    '''
    def __call__(self,*args):
        return numpy.array([i.rvs(random_state=self.random_state) for i in self.dists])


class GaussAndFlip(HoppingSteps):
    u'''for two calls, one uses defined dists
    the other randomly flips 2 consecutive xstates
    '''
    def __init__(self,**kwargs):
        super().__init__(**kwargs)
        self.count = 0
    def __call__(self,xst):
        if self.count==0:
            self.count=1
            return numpy.array([i.rvs(random_state=self.random_state) for i in self.dists])
        else:
            self.count=0
            flip = numpy.random.randint(len(xst)-1)
            xst[flip], xst[flip+1] = xst[flip+1],xst[flip]
            return xst

class OptimOligoSwap(HoppingSteps): # not yet usable
    u'''
    trying to optimize the exploration of param space given hypotheses:
    symetric distribution of z around z0 (gaussian at the moment)
    find the distribution which overlap (and allow permutation of oligos)

    # segregate per batch permutation beteen oligos with same batch_id is forbidden
    # -> better for recursive, scaffolding
    # segregate per batch permutation beteen oligos with same sequence is forbidden

    # strategies:
    # find each groups of oligos, take itertools.product(groups) find overlaps is too long!
    # find overlapping oligos, find different groups for each overlapping set
    '''
    def __init__(self,**kwargs):
        super().__init__(**kwargs)
        self.oligos = kwargs.get("oligos",[])
        self.nscale = kwargs.get("nscale",1)
        self.seg = kwargs.get("seg","batch_id") # "batch", "sequence"
        # find overlapping oligos
        # for each overlapping group, find the different groups, within overlapping oligos
        #overoli = utils.find_overlapping_oligos(self.oligos,nscale=nscale)
        #self.perms = []
        #for overgrp in overoli:
        #    groups = utils.group_oligos(overgrp,by=self.seg)
        #    print("len(groups)=",len(groups))
        #    for pro in itertools.product(*groups):
        #        self.perms.append(pro) # perms contains duplicate permutations

        # set the calls such that __call__ tends to merge batches together 
        batches = set(i.batch_id for i in self.oligos)
        groups = utils.group_oligos(,by=self.seg)

    def __call__(self,xst):
        u'''
        at each call 2 batch_ids are merged
        '''
        
        
class NestedAsmrs:
    u'''
    nested Monte Carlo running different random seeds in parallel
    should update the temperature based on each asmrs
    '''
    def __init__(self,**kwargs):
        u'''
        duplicate an Assembler object for different seeds value
        '''
        self.nprocs = kwargs.get("nprocs",1) # type: int
        self.seeds = kwargs.get("seeds",[]) # type: Iterable[int]
        self.asmrs = kwargs.get("asmrs",[]) # Assemblers
        for idx,val in enumerate(self.seeds):
            self.asmrs[idx].npstate = numpy.random.RandomState(val)
        self.T = kwargs.get("T",1.0) # pylint:disable=invalid-name
        self._pool = None
        if self.nprocs>1:
            try:
                self._pool = Pool(processes=self.nprocs)
            except OSError:
                print("could not create Pool")
                self._pool = None

    def __del__(self,):
        u'closes pool'
        if not self._pool is None:
            self._pool.close()

    def run(self,niter:int=1):
        u'''run in parallel each asmrs
        '''
        if self._pool is None:
            for asmr in self.asmrs:
                asmr.run(niter=niter,T=self.T)
        else:
            self.asmrs = self._pool.map(_run_asmr,
                                        [(asmr,{"niter":niter,"T":self.T}) for asmr in self.asmrs])

    @property
    def result(self):
        u'''results for each of the assemblers'''
        return [asmr.result for asmr in self.asmrs]

    def __getstate__(self):
        u'for pickling'
        self_dict = self.__dict__.copy()
        del self_dict["_pool"]
        return self_dict

    def __setstate__(self,state):
        u'reassign nprocs worker to the _pool'
        try:
            _pool = Pool(processes=state["nprocs"])
        except OSError:
            print("could not create Pool")
            _pool = None
        state.update({"_pool":_pool})
        self.__dict__=state # pylint: disable=attribute-defined-outside-init

def _run_asmr(*args):
    asmr=args[0][0]
    asmr.run(**args[0][1])
    return asmr



def adjust_T(nested:NestedAsmrs):
    u'modifies the temperature of the NestedAsmrs to increase mixing'
    # read fun values
    all_fun = [i.fun for i in nested.result]
    all_fun.sort()
    nested.T = all_fun[-1]-all_fun[0]

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
            self.npstate = None
        else:
            self.npstate = numpy.random.RandomState(seed)

    def run(self,*args,**kwargs):
        u'runs the assembler'
        pass

class MCAssembler(Assembler):
    u'''
    Monte Carlo for assembling sequences from oligohits
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
        if self.state is None:
            self.state=self.state_init

        count = self.result.it if hasattr(self.result,"it") else 0
        self.step.random_state=self.npstate
        self.result = basinhopping(self.func,
                                   self.state,
                                   take_step=self.step,
                                   accept_test=self.acceptance,
                                   minimizer_kwargs=dict(method=self.minimizer),
                                   callback=self.callback,
                                   **kwargs)
        self.result.it = count+kwargs.get("niter")
        self.npstate = self.step.random_state # get_state from the distribution
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


def force_accept(*args,**kwargs):# pylint: disable=unused-argument
    u'for testing purposes'
    return "force accept"
