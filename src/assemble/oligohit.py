#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u'''
Creates Classes and function to use with assemble sequence
'''


def sequence2oligohits(seq,size,overlap):
    u'''given a sequence, size and overlap of oligos returns a list corresponding oligohits'''
    # compute sequences of oligos
    oliseqs = [seq[i:i+size]for i in range(0,len(seq),size-overlap)]
    return [OligoHit(val,
                     idx*(size-overlap),
                     idx*(size-overlap)) for idx,val in enumerate(oliseqs)]


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

    def noverlaps(self,other)->int:
        u'''
        given the position (bpos) of each oligo
        return the number overlapping bases (str) between the two
        '''
        shift=other.bpos-self.bpos

        return noverlaps(self.seq,other.seq,shift=shift)
