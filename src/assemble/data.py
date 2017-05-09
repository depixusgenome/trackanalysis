#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u'''
Creates Classes and function to use with assemble sequence
'''
from typing import List, NamedTuple, Tuple
import itertools
import numpy
from utils import initdefaults
from ._types import SciDist # pylint: disable=unused-import
from . import _utils as utils


class Oligo:
    u'''
    container for an oligo sequence, a position in nanometer
    and a position in base
    '''
    seq="" # type: str
    pos=-1 # type: int
    bpos=-1 # type: int # base position
    @initdefaults
    def __init__(self,**kwa):
        pass
    @property
    def size(self):
        u'returns len(seq)'
        return len(self.seq)

    @staticmethod
    def tail_overlap(ol1:str, ol2:str)->str:
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
    batch_id = -1 # type: int
    dist = None # type: SciDist
    poserr = -1. # type: float
    # initial (experimental) position in nanometer
    pos0 = -1. # type : float
    # initial (experimental) base position
    bpos0 = -1. # type : float
    @initdefaults
    def __init__(self,**kwa):
        super().__init__(**kwa)

OliBat = NamedTuple("OliBat",[("oli",OligoPeak),
                              ("idinbat",int),
                              ("batid",int)])

class Batch:
    u'''
    Container for Oligo
    '''
    oligos=[] # type: List[OligoPeak]
    index=-1 # type: int
    @initdefaults
    def __init__(self,**kwa):
        pass

    def fill_with(self,other)->None:
        u'adds oligos from other into self and empties other'
        self.oligos.extend(other.oligos)
        del other.oligos

    def oligo_overlap(self,other,min_overl:int=1)->bool:
        u'''
        compare the sequences of oligos in the two batch
        if any can tail_overlap
        return True
        else return False
        '''
        oli1 = set(oli.seq for oli in self.oligos)
        oli2 = set(oli.seq for oli in other.oligos)
        for ite in itertools.product(oli1,oli2):
            if len(Oligo.tail_overlap(ite[0],ite[1]))>=min_overl:
                return True
            if len(Oligo.tail_overlap(ite[1],ite[0]))>=min_overl:
                return True

        return False

class BCollection:
    u'''
    Collection of batches
    '''
    oligos = [] # type: List[OligoPeak]
    batches = [] # type: List[Batch]
    @initdefaults
    def __init__(self,**kwa):
        pass

    @classmethod
    def from_oligos(cls,oligos:List[OligoPeak],attr="seq"): # read process (to processor)?
        u'from a list of OligoPeaks, creates BCollection'
        grps= {getattr(oli,attr) for oli in oligos}
        batches=[Batch(oligos=[oli for oli in oligos if getattr(oli,attr)==grp],index=idx)
                 for idx,grp in enumerate(grps)]
        return cls(oligos=oligos,batches=batches)

    def group_overlapping_oligos(self,nscale)->List[List[OligoPeak]]:
        u'returns groups of overlapping oligos'
        groups = utils.group_overlapping_normdists([oli.dist for oli in self.oligos],
                                                   nscale=nscale)[1]
        return [[self.oligos[idx] for idx in grp] for grp in groups]

    def group_overlapping_batches(self,nscale)->List[List[OligoPeak]]:
        u'same as group_overlapping_oligos except that only oligos in batches are considered'
        olis=[] # type: List[OligoPeak]
        for bat in self.batches:
            olis+=bat.oligos
        groups = utils.group_overlapping_normdists([oli.dist for oli in olis],
                                                   nscale=nscale)[1]
        return [[olis[idx] for idx in grp] for grp in groups]


    def oli2index(self,oli:OligoPeak)->int:
        u'returns index of oli in oligos'
        return self.oligos.index(oli)

class KPerm:
    u'''k-permutation is a partial permutation'''
    def __init__(self,kperm:Tuple)->None:
        self.kperm=kperm
    def to_perm(self,size):
        u'returns Perm'
        perm = Perm(size)
        perm.from_kperm(self)
        return perm

class Perm:
    u'class to permutation'
    def __init__(self,size:int)->None:
        self.size=size
        self.perm=numpy.array(range(size)) # defaults to neutral permutation
    def from_kperm(self,kperm:KPerm):
        u'translate a kperm of 2 or more indices to a full size permutation'
        toperm={val:kperm.kperm[idx] for idx,val in enumerate(sorted(kperm.kperm))}
        for key,val in toperm.items():
            self.perm[key]=val
