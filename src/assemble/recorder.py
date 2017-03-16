#!/usr/bin/env python3
# -*- coding: utf-8 -*-

u'''
regroups functions and classes to initialise recorders
'''

from typing import Callable, Iterable # pylint: disable=unused-import
import pickle
import pandas
import numpy
from . import oligohit
from . import asm

class Recorder:
    u'''
    keeps the results the assembler at each time step
    '''
    def __init__(self,**kwargs): # ok
        self.assembler = kwargs.get("assembler",None)
        self.rec = kwargs.get("rec",[]) # list of results
        self.filename = kwargs.get("filename","")

    def run(self,*args,**kwargs): # ok
        u'calls assembler and save the result'
        self.assembler.run(*args,**kwargs)
        self.rec.append(self.assembler.result)

    def to_pickle(self):
        u'saves the rec list to pickle file'
        with open(self.filename,"wb") as out_file:
            pickle.dump(self,out_file)

    def get_state(self,idx,idx2=0):
        u'returns state of simulations at index idx'
        try:
            return self.rec[idx].x
        except IndexError:
            return []
        except AttributeError:
            return self.rec[idx][idx2].x

    def get_curr_state(self,idx2=0):
        u'returns the current state of the simulation'
        return self.get_state(-1,idx2)

    def last_fun(self): # to fix for nested asmrs
        u'returns last fun value and numpy.nan if rec is empty'
        try:
            return self.rec[-1].fun
        except IndexError:
            return numpy.nan

    def to_pandas(self):
        u'''
        returns the records under a DataFrame to analyse the results
        '''
        data = pandas.DataFrame()
        if isinstance(self.assembler,asm.Assembler):
            for elm in self.rec:
                to_dict = _OResult_to_Series(elm)
                data = data.append(to_dict,ignore_index=True)
        elif isinstance(self.assembler,asm.NestedAsmrs):
            for rec_it in self.rec:
                for asm_id,elm in enumerate(rec_it):
                    to_dict = _OResult_to_Series(elm)
                    to_dict["asm_id"] = asm_id
                    to_dict["npseed"] = self.assembler.seeds[asm_id]
                    data = data.append(to_dict,ignore_index=True)
        return data

def _OResult_to_Series(elm):
    u'modifies slightly the OptimizeResult dict'
    to_dict = dict(elm)
    del to_dict["lowest_optimization_result"]
    del to_dict["message"]
    return pandas.Series(to_dict)


class SeqRecorder(Recorder):
    u'''
    adds information (sequence, oligohits) to a Recorder
    '''
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.sequence = kwargs.get("sequence","")
        self.oligohits = kwargs.get("oligohits",[])

    def get_oligohits(self,idx1,idx2=0):
        u'returns oligohits at mcmc step idx'
        pos = self.get_state(idx1,idx2)
        return [oligohit.OligoHit(seq=val.seq,
                                  pos=pos[idx],
                                  pos0=val.pos0,
                                  bpos=val.bpos,
                                  bpos0=val.bpos0)\
                for idx,val in enumerate(self.oligohits)]

    def get_curr_oligohits(self,idx2=0):
        u' returns olighits with the current state value'
        return self.get_oligohits(-1,idx2)
