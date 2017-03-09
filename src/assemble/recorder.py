#!/usr/bin/env python3
# -*- coding: utf-8 -*-

u'''
regroups functions and classes to initialise recorders
'''

from typing import Callable, Iterable # pylint: disable=unused-import
import pickle
import copy
import numpy
from . import oligohit
from . import asm_utils


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
