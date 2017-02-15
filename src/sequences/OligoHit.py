#!/usr/bin/env python3
# -*- coding: utf-8 -*-

u'''
Creates Classes and function to use with assemble sequence
'''

def noverlap_bpos(ol1,ol2)->int: # to optimize # to test # to unit-test
    u'''
    given the position (bpos) of each oligo
    return the number overlapping bases (str) between the two
    '''
    if ol1.bpos>ol2.bpos:
        ol1,ol2=ol2,ol1

    idx2 = int(ol2.bpos-ol1.bpos)
    if ol1.size<idx2:
        return 0

    seq1=ol1.seq[idx2:idx2+ol2.size]
    seq2=ol2.seq
    return [c1==c2 for c1,c2 in zip(seq1,seq2)].count(True)

def tail_overlap(ol1:str, ol2:str)->str:
    u'''
    returns ol1[j:] if ol1[j:]==ol2[:len(ol1)-i]
    '''
    for i in range(len(ol1)):
        if ol1[i:]==ol2[:len(ol1)-i]:
            return ol1[i:]
    return ''

def max_tail_overlap(ol1:str, ol2:str)->str:
    u'''
    returns maximal overlap of tail_overlap(ol1:str, ol2:str) , tail_overlap(ol2:str, ol1:str)
    '''
    tail1 = tail_overlap(ol1, ol2)
    tail2 = tail_overlap(ol2, ol1)
    if len(tail1)>len(tail2):
        return tail1
    return tail2


class OligoHit:
    u'''
    container for an oligo sequence, a position in nanometer
    and a position in base
    '''
    def __init__(self,seq:str,pos:float,bpos:int,**kwargs)->None:
        self.pos=pos # position in nanometer
        self.bpos=int(bpos) # base position
        self.seq=seq # the oligo sequence
        self.size=len(seq)
        self.batch_id=kwargs.get("batch_id",None)
