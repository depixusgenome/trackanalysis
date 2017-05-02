#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u'''
Creates Classes and function to use with assemble sequence
'''
from typing import List
from utils import initdefaults
import itertools

class Oligo:
    u'''
    container for an oligo sequence, a position in nanometer
    and a position in base
    '''
    seq:str=""
    pos:int=-1
    bpos:int=-1 # base position
    @initdefaults
    def __init__(self,**kwa):
        pass
    @property
    def size(self):
        return len(self.seq)

    def overlap_with(self,other:Oligo):
        Oligo.__tail_overlap(self.seq,other.seq)

    @staticmethod
    def __tail_overlap(ol1:str, ol2:str)->str:
        u'''
        returns the end sequence of ol1 matching the start of ol2
        '''
        for i in range(len(ol1)):
            if ol1[i:]==ol2[:len(ol1)-i]:
                return ol1[i:]
        return ""

    def add_to_sequence(self,seq:str)->str:
        u'''
        returns the sequence such that overlap of seq and oseq is maximised
        '''
        if self.seq=="":
            return seq
        i=0 # if seq==""
        for i in range(len(seq)):
            if seq[i:]==self.seq[:len(seq)-i]:
                return seq[:i]+self.seq
        return seq+self.seq
        
class OligoPeak(Oligo):
    u'represents peaks obtained from sequencing experiment'
    batch_id:int=-1
    dist=kwa.get("dist",None)# type: List
    poserr:float=-1.
    pos0:float=-1. # initial (experimental) position in nanometer
    bpos0:float=-1. # initial (experimental) base position
    @initdefaults
    def __init__(self,**kwa):
        super().__init__(**kwa)

class Batch:
    u'''
    Container for Oligo
    '''
    oligos:List[OligoPeak]=[]
    index:int=-1
    @initdefaults
    def __init__(self,**kwa):
        pass

    def fill_with(self,other:Batch)->None:
        u'adds oligos from other into self and empties other'
        self.oligos.extend(other.oligos)
        del other.oligos

    def oligo_overlap(self,other:Batch,min_overl:int=1)->bool:
        u'''
        compare the sequences of oligos in the two batch
        if any can tail_overlap
        return True
        else return False
        '''
        oli1 = set(oli.seq for oli in self.oligos)
        oli2 = set(oli.seq for oli in other.oligos)
        for ite in itertools.product(oli1,oli2):
            if len(Oligo.__tail_overlap(ite[0],ite[1]))>=min_overl:
                return True
            if len(Oligo.__tail_overlap(ite[1],ite[0]))>=min_overl:
                return True

        return False

class BCollection:
    u'''
    Collection of batches
    '''
    oligos:List[OligoPeak] = []
    batches:List[Batch] = []
    @initdefaults
    def __init__(self,**kwa):
        pass

    def from_oligos(self,oligos): # read process (to processor)?
        u''
        grps= {getattr(oli,attr) for oli in oligos}
        batches=[Batch(oligos=[oli for oli in self.oligos if getattr(oli,attr)==grp],index=idx)
                 for idx,grp in enumerate(grps)]
        self.__init__(oligos=oligos,batches=batches)
