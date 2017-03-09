#!/usr/bin/env python3
# -*- coding: utf-8 -*-

u'''
regroups functions and classes to initialise assemblers
'''

import sys
from typing import Callable, Iterable # pylint: disable=unused-import
import pickle
import copy
from multiprocessing import Pool
import numpy
from scipy.optimize import basinhopping,OptimizeResult
from scipy.stats import truncnorm
from . import oligohit
from . import asm_utils

# needs fixing : each object should be pickable
#                test NestedAsmrs

# Fixed parameters
# bp_to_nm = 1.100

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
        self.asmrs = [copy.deepcopy(self.asmr_init) for i in self.asmr_init]
        for idx,val in enumerate(self.seeds):
            self.asmrs[idx].npstate = numpy.random.RandomState(val).get_state()
        try:
            self._pool = Pool(processes=nprocs)
        except OSError:
            print("could not create Pool")
            self._pool = None

    def run(self,nsteps:int=1):
        u'run in parallel each asmrs'
        if self._pool is None:
            for asm in self.asmrs:
                asm.run(nsteps)
        else:
            self._pool.map(_run_asm,[(asm,nsteps) for asm in self.asmrs]) # check this

    def result(self):
        u'''needs to return a result to use Recorder
        is it really needed? '''
        pass

def _run_asm(asmr:Assembler,nsteps)->None:
    asmr.run(nsteps)

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
        nsteps = kwargs.get("nsteps",1)
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
                                   niter=nsteps,
                                   **kwargs)
        self.result.it = count+nsteps

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

class Recorder:
    u'''
    keeps the results the assembler at each time step
    '''
    def __init__(self,**kwargs):
        self.assembler = kwargs.get("assembler",None)
        self.rec = kwargs.get("rec",[]) # list of results
        self.filename = kwargs.get("filename","")

    def run(self):
        u'calls assembler and save the result'
        self.assembler.run()
        self.rec.append(self.assembler.result)

    def to_pickle(self):
        u'saves the rec list to pickle file'
        with open(self.filename,"wb") as out_file:
            pickle.dump(self.rec,out_file)

    def get_state(self,idx):
        u'returns state of simulations at index idx'
        try:
            return self.rec[idx].x
        except IndexError:
            return []

    def get_curr_state(self):
        u'returns the current state of the simulation'
        return self.get_state(-1)

    def last_fun(self):
        u'returns last fun value and numpy.nan if rec is empty'
        try:
            return self.rec[-1].fun
        except IndexError:
            return numpy.nan

class SeqRecorder(Recorder):
    u'''
    adds information (sequence, oligohits) to a Recorder
    '''
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.sequence = kwargs.get("sequence","")
        self.oligohits = kwargs.get("oligohits",[])

    def to_pickle(self):
        u'''
        temp solution to deal with wrapped function not pickling
        pickles information to reconstruct the SeqRecorder
        '''
        sr_pickler = _SeqRecPickler(seqr=self)
        sr_pickler.to_pickle(self.filename)

    def get_oligohits(self,idx):
        u'returns oligohits at mcmc step idx'
        pos = self.get_state(idx)
        return [oligohit.OligoHit(seq=val.seq,
                                  pos=pos[idx],
                                  pos0=val.pos0,
                                  bpos=val.bpos,
                                  bpos0=val.bpos0)\
                for idx,val in enumerate(self.oligohits)]

    def get_curr_oligohits(self):
        u' returns olighits with the current state value'
        return self.get_oligohits(-1)

    @classmethod
    def from_pickle(cls,picklename,energy_func,tooligo_func):
        u'''
        temp function to deal with wrapped function not pickling.
        Creates a new seqRecorder object
        '''
        try:
            with open(picklename,"rb") as outfile:
                sr_pickler = pickle.load(outfile)
                # reconstruct class from loaded class
                return sr_pickler.to_seqrecorder(energy_func,tooligo_func)
        except EOFError:
            return cls()


class _SeqRecPickler:
    u'''
    temp class used as a work around unpicklable function
    '''

    def __init__(self,seqr:SeqRecorder)->None:
        self.rec = copy.deepcopy(seqr.rec) # list of results
        self.filename = seqr.filename
        self.sequence = seqr.sequence
        self.oligohits =  copy.deepcopy(seqr.oligohits)
        # pop func which does not pickle
        asr_atr =  copy.deepcopy(seqr.assembler.__dict__)
        asr_atr.pop("func")
        self.assembler = seqr.assembler.__class__(**asr_atr)

    def to_pickle(self,picklename):
        u''' simple pickle
        '''
        with open(picklename,"wb") as outfile:
            pickle.dump(self,outfile)

    @classmethod
    def from_pickle(cls,picklename):
        u'''
        simple load from pickle
        '''
        with open(picklename,"rb") as outfile:
            seqrpickler=pickle.load(outfile)
        return seqrpickler

    def to_seqrecorder(self,energy_func,tooligo_func)->SeqRecorder:
        u'''
        reconstructs a SeqRecorder object
        '''
        asr_atr = self.assembler.__dict__
        # update asr_dict with wrapped func
        wrapper = asm_utils.OligoWrap(self.oligohits,tooligo_func)
        wrpfunc = wrapper(energy_func) # eg noverlaps_energy
        asr_atr.update({"func":wrpfunc})
        assembler = self.assembler.__class__(**asr_atr)
        seqr_atr = self.__dict__
        seqr_atr["assembler"] = assembler
        return SeqRecorder(**seqr_atr)
