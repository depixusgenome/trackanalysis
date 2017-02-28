#!/usr/bin/env python3
# -*- coding: utf-8 -*-

u'''
regroups functions and classes to assemble a sequence
'''

import sys
from itertools import combinations
from copy import deepcopy
from typing import Callable # pylint: disable=unused-import
import pickle
import numpy
from scipy.optimize import basinhopping,OptimizeResult
from scipy.stats import truncnorm
from utils import initdefaults
from Bio import pairwise2
from . import oligohit

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

class OligoWrap:
    u'''
    decorator for use of bpos array instead of list of oligohit
    '''
    def __init__(self,oligos,wrapping):
        u'''
        wrapping is a function whci returns new oligos from *args
        ex: wrapping = bpos2oligos, pos2oligos
        '''
        self.oligos=oligos
        self.wrapping=wrapping

    def __call__(self,func):
        u'''returns a function which takes new positions of oligos
        instead of new oligos
        required for basinhopping
        '''
        def wrapped_func(*args):
            u'''
            wrapper
            '''
            oligos=self.wrapping(self.oligos,*args)
            return func(oligos)
        return wrapped_func

def pos2oligos(olis,pos): # formerly oligos_from_pos
    u'''
    returns a function which takes an array of pos instead of oligos
    '''
    assert len(olis)==len(pos)
    oligos = [deepcopy(i) for i in olis]
    for idx,val in enumerate(pos):
        oligos[idx].pos=val
    return oligos

def bpos2oligos(olis,bpos): # oligos_from_bpos
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

def tsl_energy(oligos):
    u'''
    energy cost related to translation of oligos away from its experimental position
    '''
    energy = 0
    for oli in oligos:
        energy+=(oli.pos-oli.pos0)**4
    return energy

def noverlaps_tsl_energy(oligos,ratio=0.01):
    # can't use as is because of relationship between bpos and pos
    u'''
    computes the energy of overlapping oligos
    and a penalty for translation of oligos position
    ratio=0.01, is the ratio between the two energies
    ratio is such that tsl/noverlaps should be comparable
    '''
    energy = noverlaps_energy(oligos)
    energy += ratio*tsl_energy(oligos)
    return energy

def tail_tsl_energy(oligos,ratio=0.01):
    u'''
    computes the energy of tail overlapping oligos
    and a penalty for translation of oligos position
    ratio=0.01, is the ratio between the two energies
    ratio is such that tsl/noverlaps should be comparable
    '''
    energy = tail_overlap_energy(oligos)
    energy += ratio*tsl_energy(oligos)
    return energy

def tail_overlap_energy(oligos)->float:
    u'''
    sort by pos and apply tail_overlap
    '''
    oligo_sort = sorted(oligos,key=lambda x :x.pos)
    overlaps = numpy.array([len(oligohit.tail_overlap(oli.seq,oligo_sort[idx+1].seq))\
                        for idx,oli in enumerate(oligo_sort[:-1])])
    return -sum(overlaps[overlaps!=numpy.array(None)]**2)

def acceptance(): # could implement
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
    niter = 1 # type: int
    result = OptimizeResult()
    step = HoppingSteps()

    @initdefaults
    def __init__(self,**_):
        pass

    def run_nsteps(self,nsteps:int,**_)->None:
        u'''runs a specified number of steps
        '''
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
                                   **_)
        self.result.it = count+nsteps
        self.update(self.result)

    def run(self):
        u'runs niter steps'
        self.run_nsteps(self.niter)

    def update(self,result:OptimizeResult):
        u'''
        update the simulator from result
        '''
        self.state = result.x


class Recorder:
    u'''
    keeps the results the assembler at each time step
    '''
    def __init__(self,*args,**kwargs):
        self.assembler = kwargs.get("assembler",None)
        self.rec = kwargs.get("rec",[]) # list of results
        self.filename = kwargs.get("filename","recorder_default")
        self.args = args # for subsequent analysis
        self.kwargs = kwargs # for subsequent analysis

    def run(self):
        u'calls assembler and save the result'
        self.assembler.run()
        self.rec.append(self.assembler.result)

    def to_pickle(self):
        u'saves the rec list to pickle file'
        with open(self.filename,"wb") as out_file:
            pickle.dump(self.rec,out_file)

    def get_curr_state(self):
        u'returns the current state of the simulation'
        return self.rec[-1].x


    #@classmethod
    #def from_pickle(cls,filename,*args,**kwargs):
    #    u'loads a rec list from pickle file'
    #    with open(filename,"rb") as in_file:
    #        return cls(rec=pickle.load(in_file))


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

    def get_curr_oligohits(self):
        u' returns olighits with the current state value'
        pos = self.get_curr_state()
        return [oligohit.OligoHit(seq=val.seq,
                                  pos=pos[idx],
                                  pos0=val.pos0,
                                  bpos=val.bpos,
                                  bpos0=val.bpos0)\
                for idx,val in enumerate(self.oligohits)]

    @classmethod
    def from_pickle(cls,picklename,energy_func):
        u'''
        temp function to deal with wrapped function not pickling.
        Creates a new seqRecorder object
        '''
        with open(picklename,"rb") as outfile:
            sr_pickler = pickle.load(outfile)
        # reconstruct class from loaded class
        return sr_pickler.to_seqrecorder(energy_func)

    def assembled_sequence(self): # to check
        u'''
        returns the assembled sequence and the shift corresponding to the oligo with lowest bpos
        '''
        curr_olis = self.get_curr_oligohits()
        bposes = [i.bpos for i in curr_olis]
        shift = min(bposes)
        size_rseq = max([i.bpos+len(i.seq) for i in curr_olis])-shift
        rseq = size_rseq*"-"
        for oli in curr_olis:
            rseq = oligohit.pile_oligo(rseq,oli,-shift)
        return rseq,shift

def match_with_sequence(seqrec:SeqRecorder):
    u'''
    given a SeqRecorder object, reconstructs the sequence given by oligos.
    return the overlap between reconstructed sequence and the sequence.
    '''
    exp_seq,shift = seqrec.assembled_sequence()
    known_seq = seqrec.sequence
    return oligohit.shifted_overlap(known_seq,exp_seq,shift)

def match_score(seqrec:SeqRecorder):
    u'''
    returns the ratio of characters in match_with_sequence not "-"
    '''
    match = match_with_sequence(seqrec)
    return 1-(match.count("-")+match.count("?"))/len(match)

class ScaleGap:
    u'rescales _gap_penalities to forbid gaps in known sequence'
    def __init__(self,value):
        self.val=value
    def __call__(self,func):
        def wrapped(*args,**kwargs):
            u'scales the output'
            return self.val*func(*args,**kwargs)
        return wrapped

def _gap_penalties(x,y): # pylint:disable=unused-argument,invalid-name
    u'''
    x, gap position in seq
    y, gap length
    '''
    if y==0:
        return 0
    return -1

def pairwise2_alignment(seqrec:SeqRecorder):
    u'''uses Bio.pairwise2 alignment to compute the best score of
    sequence from oligohits and known sequence'''
    exp_seq = seqrec.assembled_sequence()[0]
    gap_exp = ScaleGap(1)(_gap_penalties)
    gap_known = ScaleGap(1000)(_gap_penalties)
    return pairwise2.align.globalxc(seqrec.sequence,exp_seq,gap_known,gap_exp,score_only=True) # pylint: disable=no-member

class _SeqRecPickler:
    u'''
    temp class used as a work around unpicklable function
    '''

    def __init__(self,seqr:SeqRecorder)->None:
        self.rec = deepcopy(seqr.rec) # list of results
        self.filename = seqr.filename
        self.sequence = seqr.sequence
        self.oligohits =  deepcopy(seqr.oligohits)
        self.args=seqr.args
        self.kwargs=seqr.kwargs
        # pop func which does not pickle
        asr_atr =  deepcopy(seqr.assembler.__dict__)
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

    def to_seqrecorder(self,energy_func)->SeqRecorder:
        u'''
        reconstructs a SeqRecorder object
        '''
        asr_atr = self.assembler.__dict__
        # update asr_dict with wrapped func
        wrapper = OligoWrap(self.oligohits,energy_func)
        wrpfunc = wrapper(energy_func) # eg noverlaps_energy
        asr_atr.update({"func":wrpfunc})
        assembler = self.assembler.__class__(**asr_atr)
        seqr_atr = self.__dict__
        seqr_atr["assembler"] = assembler
        return SeqRecorder(**seqr_atr)
