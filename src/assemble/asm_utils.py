#!/usr/bin/env python3
# -*- coding: utf-8 -*-

u'''
regroups functions and classes to complement asm
'''

from itertools import combinations
from copy import deepcopy
from typing import Callable # pylint: disable=unused-import
import numpy
from Bio import pairwise2
from . import oligohit



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

def pos2oligos(olis,pos):
    u'''
    returns a function which takes an array of pos instead of oligos
    '''
    assert len(olis)==len(pos)
    oligos = [deepcopy(i) for i in olis]
    for idx,val in enumerate(pos):
        oligos[idx].pos=val

    return oligos

def bpos2oligos(olis,bpos):
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

def sum_tail_overlap(oligos):
    u''' returns the sum of all overlap shared by consecutive oligos
    '''
    oligo_sort = sorted(oligos,key=lambda x :x.pos)
    overlaps = numpy.array([len(oligohit.tail_overlap(oli.seq,oligo_sort[idx+1].seq))\
                        for idx,oli in enumerate(oligo_sort[:-1])])
    return sum(overlaps[overlaps!=numpy.array(None)])

def test_scaled_energies(oligos):
    u''' testing a new combination of energies
    '''
    bp_to_nm = 1.100
    energy = - bp_to_nm*sum_tail_overlap(oligos)
    energy+= 5/8*sum([abs(i.pos-i.pos0) for i in oligos]) # 1/4 should be more accurate
    return energy # could raise the power to further penalise extreme values

def test2_scaled_energies(oligos):
    u''' second test for combining energies
    '''
    bp_to_nm = 1.100
    energy = - bp_to_nm*sum_tail_overlap(oligos)
    energy += 0.25 * sum([abs(i.pos-i.pos0) for i in oligos])
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

def seq_from_bpos(srec):
    u'''
    assumes known the bpos for each oligo.
    pile the sequences
    returns the sequence and possible shift
    '''
    curr_olis = srec.get_curr_oligohits()
    bposes = [i.bpos for i in curr_olis]
    shift = min(bposes)
    size_rseq = max([i.bpos+len(i.seq) for i in curr_olis])-shift
    rseq = size_rseq*"-"
    for oli in curr_olis:
        rseq = oligohit.pile_oligo(rseq,oli,-shift)
    return rseq,shift

def max_overlap_assemble(oligos):
    u'''
    returns the sequence such that the overlap of consecutive oligos is maximised
    assuming only the orders of sorted (according to pos) oligos is correct
    '''
    if len(oligos)==0:
        return ""
    soli = sorted(oligos,key=lambda x :x.pos)
    seq=soli[0].seq
    for oli in soli[1:]:
        seq = oligohit.max_overlap_pile(seq,oli.seq)
    return seq

def match_sequence(srec,srec2seq:Callable,align_strs:Callable):
    u'''
    given a SeqRecorder object, reconstructs the sequence given by oligos using srec2seq.
    return the overlap between reconstructed sequence and the sequence.
    '''
    exp_seq = srec2seq(srec.get_curr_oligohits())
    known_seq = srec.sequence
    return align_strs(known_seq,exp_seq)

def score_match(srec,srec2seq:Callable,align_strs:Callable):
    u'''
    returns the ratio of characters in match_sequence not "-"
    '''
    match = match_sequence(srec,srec2seq,align_strs)
    if len(match)==0:
        return numpy.nan
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

def pairwise2_alignment(seqrec): # uses bpos
    u'''uses Bio.pairwise2 alignment to compute the best score of
    sequence from oligohits and known sequence'''
    exp_seq = seq_from_bpos(seqrec)[0]
    gap_exp = ScaleGap(1)(_gap_penalties)
    gap_known = ScaleGap(1000)(_gap_penalties)
    return pairwise2.align.globalxc(seqrec.sequence,exp_seq,gap_known,gap_exp,score_only=True) # pylint: disable=no-member
