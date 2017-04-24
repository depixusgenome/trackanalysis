#!/usr/bin/env python3
# -*- coding: utf-8 -*-

u'''
regroups functions and classes to complement assembler
'''

import itertools
from copy import deepcopy
from typing import Callable, List, Dict # pylint: disable=unused-import
import scipy.stats
import numpy
from Bio import pairwise2
from . import oligohit

class OligoWrap:
    u'''
    functor to convert function taking array as input into function taking oligohits
    '''
    def __init__(self,oligohits,arr2oligohits,to_call):
        u'''
        oligohits, list of original oligohits (contains sequence)
        arr2oligohits, function converting array into new oligohits
        to_call, function taking oligohits
        '''
        self.oligohits = oligohits
        self.arr2oligohits = arr2oligohits # type: Callable
        self.to_call = to_call # type: Callable
    def __call__(self,*args):
        u'''returns a function which takes new positions of oligos
        instead of new oligos
        required for basinhopping
        '''
        oligos = self.arr2oligohits(self.oligohits,*args)
        return self.to_call(oligos)

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
    for ol1,ol2 in itertools.combinations(oligos,2):
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

def test3_scaled_energies(oligos):
    u'''third test for combining energies
    '''
    bp_to_nm = 1.100
    # sorted oligos
    solis = sorted(oligos,key=lambda x :x.pos)
    overlaps = bp_to_nm*numpy.array([len(oligohit.tail_overlap(vx.seq,solis[ix+1].seq))/vx.poserr\
                                     for ix,vx in enumerate(solis[:-1])])
    overlaps = numpy.hstack((overlaps,0))
    tsl_e = numpy.array([((i.pos-i.pos0)/i.poserr)**2 for i in solis]) # khi2
    return sum(-overlaps**2+tsl_e)


def test4_scaled_energies(oligos):
    u'''
    can work with (log) probabilities only
    '''
    # sorted oligos
    solis = sorted(oligos,key=lambda x :x.pos)
    proba_tsl = numpy.array([scipy.stats.norm(loc=i.pos0,scale=i.poserr).logpdf(i.pos)\
                             for i in solis]).sum()
    overlaps = numpy.array([len(oligohit.tail_overlap(vx.seq,solis[ix+1].seq))/vx.poserr\
                            for ix,vx in enumerate(solis[:-1])])
    prob_overl = -(0.25)**sum(overlaps) # taylor decomposition
    return -proba_tsl-prob_overl

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

def match_sequence(srec,srec2seq:Callable,align_strs:Callable,asmrid:int=0):
    u'''
    given a SeqRecorder object, reconstructs the sequence given by oligos using srec2seq.
    return the overlap between reconstructed sequence and the sequence.
    '''
    exp_seq = srec2seq(srec.get_curr_oligohits(asmrid))
    known_seq = srec.sequence
    return align_strs(known_seq,exp_seq)

def score_match(srec,srec2seq:Callable,align_strs:Callable,asmrid:int=0):
    u'''
    returns the ratio of characters in match_sequence not "-"
    '''
    match = match_sequence(srec,srec2seq,align_strs,asmrid)
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


def _solver_norm_intersect(dist1,dist2):
    u'returns the x-values of intersecting normal distributions'
    sc1=dist1.std()
    mea1=dist1.mean()
    sc2=dist2.std()
    mea2=dist2.mean()

    coef1 = 1/(2*sc1**2) -1/(2*sc2**2)
    coef2 = mea2/(sc2**2)-mea1/(sc1**2)
    coef3 = mea1**2/(2*sc1**2) -mea2**2/(2*sc2**2) -numpy.log(sc2/sc1)
    return numpy.roots([coef1,coef2,coef3])

def _highest_norm_intersect(dist1,dist2):
    sc_dist=[(dist1.pdf(xval),xval) for xval in _solver_norm_intersect(dist1,dist2)]
    sc_dist.sort()
    return sc_dist[-1][1]

def group_overlapping_normdists(dists,nscale=1): # to pytest !! # what if no intersection?
    u'''
    returns lists of indices [(i,j,k)] each element of the tuple has distribution which overlap
    '''
    sdists=[(di.mean(),di.mean()-nscale*di.std(),di.mean()+nscale*di.std(),idx)\
            for idx,di in enumerate(dists)]
    sdists.sort()

    bounds = [(di.mean()-nscale*di.std(),idx) for idx,di in enumerate(dists)]
    bounds+= [(di.mean()+nscale*di.std(),idx) for idx,di in enumerate(dists)]
    bounds.sort()
    overlaps=[]
    for regid in range(len(bounds[:-1])):
        beflag = set(idx[1] for idx in bounds[:regid+1])
        aflag = set(idx[1] for idx in bounds[regid+1:])

        overlaps.append(sorted(beflag.intersection(aflag)))

    ssets = [set(overl) for overl in overlaps if len(overl)>1]
    ssets.sort(reverse=True)
    if len(ssets)==0:
        return ssets,[]
    uset=[ssets[0]]
    for val in ssets[1:]:
        if val.issubset(uset[-1]):
            continue
        uset.append(val)
    return ssets,uset



def _list_perm_bounds(perm,dists,_epsi=0.001):
    u'list of possible positions which allow (any or no) switchs between oligo positions'
    # list all possibilities
    bounds={idx:[dists[idx].mean()] for idx in perm}
    for idi,vli in enumerate(perm[:-1]):
        for vlj in perm[idi+1:]:
            flag = _highest_norm_intersect(dists[vli],dists[vlj])
            sign = 1 if dists[vli].mean()<dists[vlj].mean() else -1
            bounds[vli].append(flag+sign*_epsi)
            bounds[vlj].append(flag-sign*_epsi)
    return bounds

def optimal_perm_normdists(perm:List,dists)->numpy.ndarray: # pytest
    u'''
    given a permuation perm and the known distributions of each state
    returns the permutated state which maximise the probability
    '''
    _epsi = 0.001*min([dists[i].std() for i  in perm])

    constraints = []
    for idx in range(len(perm[:-1])):
        constraints.append({"type":"ineq",
                            "fun":SOMConstraint(idx,_epsi)})

    xinit = [dists[i].mean() for i in perm]
    fun = CostPermute(dists,perm)
    return scipy.optimize.minimize(fun,xinit,constraints=constraints).x

def group_overlapping_oligos(oligos,nscale=1):
    u'''
    returns groups of overlapping oligos
    '''
    groups = group_overlapping_normdists([oli.dist for oli in oligos],nscale=nscale)[1]
    return [[oligos[idx] for idx in grp] for grp in groups]

def group_oligos(oligos,**kwa)->Dict: # pytest!
    u''' returns dictionnary of oligos grouped by attr "by"
    '''
    byattr = kwa.get("by","batch_id")
    attr = set([getattr(oli,byattr) for oli in oligos])
    grouped = {atv:[oli for oli in oligos if getattr(oli,byattr)==atv] for atv in attr}
    return grouped

class CostPermute:
    u' returns the "cost" of translations due to permutation of oligo peaks'
    def __init__(self,dists,perm):
        self.dists = dists
        self.perm = perm

    def __call__(self,xstate):
        return -numpy.product([self.dists[vlp].pdf(xstate[idp])
                               for idp,vlp in enumerate(self.perm)])


class SOMConstraint:
    u'functor for scipy.optimize.minimize constraints'
    def __init__(self,index,_epsi):
        self.index=index
        self._epsi=_epsi
    def __call__(self,xstate):
        return xstate[self.index+1]-xstate[self.index]-self._epsi

def swap_between_batches(bat1, bat2, nscale=1): # not great impl # to optimize
    u'''
    compute all possibles swaps between batch1 and batch2
    need to rethink the algorithm.
    We assume must constraints the number of permutations as soon as possible
    batches between oligos from different batches only
    '''

    groups = group_overlapping_oligos(list(bat1.oligos)+list(bat2.oligos),nscale=nscale)
    infogrp=[]
    for grp in groups:
        info=[]
        for elmt in grp:
            try:
                info.append((elmt,bat1.oligos.index(elmt),1))
            except ValueError:
                info.append((elmt,bat2.oligos.index(elmt),2))
        infogrp.append(info)

    # remove groups if there is not a representative of the two batches
    infogrp = [i for i in infogrp if len(set(j[2] for j in i))>1]

    # ok-ish up to here
    stop
    perms=[]
    for grp in infogrp:
        print("len(grp)=",len(grp))
        for perm in itertools.permutations(grp):
            # if 2 oligos within a batch are permuted, remove permutation
            # in bat1
            if sorted([j[1] for j in perm if j[2]==1])==[j[1] for j in perm if j[2]==1]\
               and len([j[1] for j in perm if j[2]==1])>1:
                continue

            # in bat2
            if sorted([j[1] for j in perm if j[2]==2])==[j[1] for j in perm if j[2]==2]\
               and len([j[1] for j in perm if j[2]==2])>1:
                continue
            perms.append(perm)

    return [[s[0] for s in elmt] for elmt in perms]


def can_oligos_overlap(bat1:oligohit.Batch,bat2:oligohit.Batch,min_overl=1):
    u'''
    compare the sequences of oligos in the two batch
    if any can tail_overlap
    return True
    else return False
    '''
    oli1 = set(oli.seq for oli in bat1.oligos)
    oli2 = set(oli.seq for oli in bat2.oligos)
    for ite in itertools.product(oli1,oli2):
        if len(oligohit.tail_overlap(ite[0],ite[1]))>=min_overl:
            return True
        if len(oligohit.tail_overlap(ite[1],ite[0]))>=min_overl:
            return True

    return False

