#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u'''
Creates Classes and function to use with assemble sequence
'''

from typing import Callable

def shifted_overlap(ol1:str,ol2:str,shift=0)->str:
    u'''
    returns '-' when the two strings mismatch
    '''
    if shift<0:
        return shifted_overlap(ol2,ol1,-shift)

    shol=ol1[int(shift):]
    return "".join([i1 if i1==i2 else "-" for i1,i2 in zip(shol,ol2)])

def noverlaps(ol1:str,ol2:str,shift=0)->int:
    u'counts the number of overlap'
    ovlp = shifted_overlap(ol1,ol2,shift)
    return len(ovlp.replace('-',''))


def tail_overlap(ol1:str, ol2:str)->str:
    u'''
    returns the end sequence of ol1 matching the start of ol2
    '''
    for i in range(len(ol1)):
        if ol1[i:]==ol2[:len(ol1)-i]:
            return ol1[i:]
    return ""

def max_overlap_pile(seq:str,oseq:str)->str:
    u'''
    returns the sequence such that overlap of seq and oseq is maximised
    '''
    if oseq=="":
        return seq
    i=0 # if seq==""
    for i in range(len(seq)):
        if seq[i:]==oseq[:len(seq)-i]:
            return seq[:i]+oseq
    return seq+oseq

def pile_oligo(seq:str,oligo,shift:int=0)->str:
    u'''
    complement sequence with matching given by oligo
    '''
    osh = oligo.bpos+shift
    for idx,val in enumerate(oligo.seq):
        rep = seq[idx+osh]
        if rep=="?":
            continue
        if rep=="-":
            seq = seq[:idx+osh]+val+seq[idx+osh+1:]
        else:
            if rep!=val:
                seq = seq[:idx+osh]+"?"+seq[idx+osh+1:]
    return seq

class Oligo:
    u'''
    container for an oligo sequence, a position in nanometer
    and a position in base
    '''
    def __init__(self,**kwa)->None:
        self.seq=kwa.get("seq","") # the oligo sequence
        self.pos=kwa.get("pos",0) # position in nanometer
        self.bpos=kwa.get("bpos",None) # base position

    @property
    def size(self):
        u'probably not very useful'
        return len(self.seq)

    def noverlaps(self,other)->int:
        u'''
        given the position (bpos) of each oligo
        return the number overlapping bases (str) between the two
        '''
        shift = other.bpos-self.bpos

        return noverlaps(self.seq,other.seq,shift=shift)

class OligoPeak(Oligo):
    u'''
    represents peaks obtained from experiment adding attributes such as :
    position error,
    modeled by a dist, a
    '''
    def __init__(self,**kwa):
        super().__init__(**kwa)
        self.batch_id=kwa.get("batch_id",None)
        self.dist=kwa.get("dist",None)# type: List
        self.poserr=kwa.get("poserr",None)
        self.pos0=kwa.get("pos0",None) # initial (experimental) position in nanometer
        self.bpos0=kwa.get("bpos0",None) # initial (experimental) base position


class Batch:
    u'''
    Container for Oligo
    '''
    def __init__(self,**kwa):
        self.oligos = kwa.get("oligos",[])
        self.index = kwa.get("index",0)

    def fill_with(self,other)->None:
        u'adds oligos from other into self and empties other'
        self.oligos.extend(other.oligos)
        del other.oligos

class CallFalse:
    def __call__(self,*args,**kwargs):
        return False
# enum for rules retriction
class BatchModel:
    u'''
    Container class which controls batches and how they interact
    '''
    def __init__(self,oligos,sort_by="pos0",**kwa):
        self.oligos=sorted(oligos,key=lambda x:getattr(x,sort_by))
        self.batches=[]
        self.can_peak_flip=kwa.get("flip_rule",CallFalse()) # type:Callable
        
    def batch_by(self,attr="seq"):
        u'create Batch with groups of similar "attr" value'
        grps = {getattr(oli,attr) for oli in self.oligos}
        self.batches=[[oli for oli in self.oligos if getattr(oli,attr)==grp] for grp in grps]

