#!/usr/bin/env python3
# -*- coding: utf-8 -*-

'''
must define non-linearity as a for each OPeakArray
use of TO FIX tags for priority commands to implement
'''

import itertools
from typing import List, Tuple, Dict, FrozenSet, Iterable # pylint:disable=unused-import
import numpy
from utils import initdefaults
import assemble.data as data
import assemble.shuffler as shuffler

BP2NM=1.1

class Bounds:
    'define upper lower limits on parameters'
    def __init__(self,lower=0,upper=0):
        self.lower=lower
        self.upper=upper

    def nisin(self,val)->bool:
        'test limits'
        if val>self.upper or val<self.lower:
            return True
        return False

class Rescale:
    'groups stretch and bias values'
    atol=0.001
    def __init__(self,stretch,bias):
        self.stre=stretch
        self.bias=bias

    def __call__(self,array):
        return self.stre*array+self.bias

    def __str__(self):
        return f'stretch {self.stre}, bias {self.bias}'

    @property
    def toarr(self):
        'array of stre,bias'
        return numpy.array(self.stre,self.bias)

    def __hash__(self):
        return hash((self.stre,self.bias))

    def __eq__(self,other):
        if isinstance(other,type(self)):
            return all(numpy.isclose(self.toarr,other.toarr,atol=self.atol))
        return False

def match_peaks(peaks1,
                peaks2,
                bound_stretch:Bounds,
                bound_bias:Bounds)->List[Rescale]:
    '''
    NEEDS TO ACCOUNT FOR PRECISION (not yet implemented,
    missing cases where bounds would discard solutions but not bounds+precision)
    if peakcalling wan take account of precision, consider peakcalling as a better alternative
    peaks1 is supposed fixed
    returns stretches and biases

    # for each index in peaks2:
    # find indices from peaks1 that are > bound_stretch.min*peaks2
    # and indices from peaks1 that are < bound_stretch.max*peaks2
    # start with lowest stretch to max stretch

    '''
    scales=[]
    # find all biases with at least 1 match
    # for all biases add all stretch values such that another match is created
    biases=[]
    for pe1 in peaks1:
        for pe2 in peaks2:
            if bound_bias.nisin(pe1-pe2):
                continue
            scales.append(Rescale(1,pe1-pe2))
            biases.append(pe1-pe2)

    for bias in list(biases):
        for pe2 in peaks2:
            upper=peaks1>=bound_stretch.lower*pe2+bias
            lower=peaks1<=bound_stretch.upper*pe2+bias
            tostretch=numpy.array(peaks1)[numpy.logical_and(upper,lower)]
            for stre in tostretch:
                scales.append(Rescale((stre-bias)/pe2,bias))

    return list(frozenset(scales))

def count_matches(peaks1,peaks2,fprecision=1e-3):
    '''
    peaks1 and peaks2 are 2 scaled arrays
    this function is asymmetric!
    '''
    count=0
    for peak in peaks1:
        if numpy.isclose(peak,peaks2,atol=fprecision).any():
            count+=1
    return count

class OPeakArray:
    '''
    corresponds to an experiment with a single oligo
    each OligoPeak can be either sequence or reverse complement sequence
    Can even include Oligo experiments with different (not reverse_complement) sequences
    '''
    arr=numpy.empty(shape=(0,),dtype=data.OligoPeak)
    min_overl=2 # type: int
    rev=data.Oligo.reverse_complement
    @initdefaults(frozenset(locals()))
    def __init__(self,**kwa):
        pass

    @staticmethod
    def from_oligos(oligos:List[data.OligoPeak])->List:
        'return Peaks from oligos'
        solis=sorted([(oli.seq,oli.pos,oli) for oli in oligos])
        exp=[]
        for values in itertools.groupby(solis,key=lambda x:x[0]):
            exp.append(OPeakArray(arr=numpy.array([oli[2] for oli in values[1]])))
        return exp

    def matching_seq(self,seq,with_reverse=True):
        '''returns the array of position which match seq'''
        if with_reverse:
            return numpy.array([i.pos for i in self.arr if i.seq==seq or self.rev(i.seq)==seq])
        return numpy.array([i.pos for i in self.arr if i.seq==seq])

    def find_matches(self,other,bstretch,bbias,with_reverse=True)->List[Rescale]:
        '''
        needs to take into account the seq of matching OligoPeaks
        stretches,biases are defined using self has (1,0)
        includes reverse_complement
        '''
        sseqs=frozenset(oli.seq for oli in self.arr)
        oseqs=frozenset(oli.seq for oli in other.arr)
        if with_reverse:
            oseqs=oseqs.union(frozenset(other.rev(oli.seq) for oli in other.arr))

        matches=[(str1,str2)
                 for str1 in sseqs
                 for str2 in oseqs
                 if len(data.Oligo.tail_overlap(str1,str2))>=self.min_overl
                 or len(data.Oligo.tail_overlap(str2,str1))>=self.min_overl]
        scales=[] # type: List[Rescale]
        for match in matches:
            arr1=self.matching_seq(match[0])
            arr2=other.matching_seq(match[1])
            scales+=match_peaks(arr1,
                                arr2,
                                bstretch,
                                bbias)
        return list(frozenset(scales))

    @property
    def posarr(self):
        'array of oligo positions'
        return numpy.array([oli.pos for oli in self.arr])

    def __rmul__(self,factor):
        kwa=dict(self.__dict__)
        kwa["arr"]=factor*kwa["arr"]
        return OPeakArray(**kwa)

    def __mul__(self,factor):
        return self.__rmul__(factor)

    def __radd__(self,bias):
        kwa=dict(self.__dict__)
        kwa["arr"]=bias+kwa["arr"]
        return OPeakArray(**kwa)

    def __add__(self,bias):
        return self.__radd__(bias)

    @property
    def seqs(self):
        'returns sequences in peakarray'
        return frozenset(i.seq for i in self.arr)

    def matching_clusters(self,scaledpeaks)->List[List]:
        '''
        groups the matching peaks into groups of OligoPeak for basewise algorithm
        '''
        if __debug__:
            print(self,scaledpeaks)
        return [[]]

    @staticmethod
    def may_overlap(peak,others:List,min_overl:int,with_reverse=True):
        '''
        compare the sequences of the 2 experiments
        returns True if the 2 sequences may overlap
        False otherwise
        if with_reverse, also considers reverse_complement
        '''
        to_match=frozenset(i.seq for i in peak.arr)
        match=[]
        for seq in to_match:
            for opk in others:
                for tocheck in opk.seqs:
                    if data.Oligo.do_overlap(seq,tocheck,min_overl):
                        match.append(opk)
                        break
                    if with_reverse and data.Oligo.do_overlap(seq,opk.rev(tocheck),min_overl):
                        match.append(opk)
                        break

        return match

    def count_matches(self,scaled,nlampli)->int:
        '''
        maximum number of matches in len(self.arr)
        asymmetric function
        '''
        return count_matches([i.pos for i in self.arr],
                             [i.pos for i in scaled.arr],
                             fprecision=nlampli)

    def __hash__(self)->int:
        'could help to implement this'
        return hash(self.arr.tobytes())

    def __eq__(self,other)->bool:
        if isinstance(other,type(self)):
            return hash(self)==hash(other)
        return False

def no_orientation(oligos:List[data.OligoPeak]):
    'each oligo has its sequence changed so that we loose the information on the orientation'
    reverse=data.Oligo.reverse_complement
    return [oli.copy(seq=min(oli.seq,reverse(oli.seq))) for oli in oligos]

# non-linearity issues should be dealt with here (and only?)
# if we do assume a fixde orientation for the refpeak,
# we reduce drastically the number of possibilities
# in this case we check if we can add a peakarray (no orientation assumed)
# orientation is fixed (peakwise and not peakarray wise) when the peakarray is added to the stack
class PeakStack:
    '''
    class to stack scaled peakarray
    adds from left to right (- to +)
    ooligos and ordered use only the positions relative to the reference peak
    to rewrite ordered is a list but for each peak in ordered[0] we have a stack
    '''
    def __init__(self,**kwa):
        # ordered list of scaled OPeakArray
        self.min_overlap=kwa.get("min_overlap",2) # type: int
        self.ordered=list(kwa.get("ordered",[])) # type: List[OPeakArray]
        self.stack=dict() # type: Dict[float,List[data.Oligo]] # make private?
        if self.ordered:
            for peakarr in self.ordered:
                self._add2stack(peakarr)

    # should include non-linearity in this method
    # could return True (instead of False) if we allow for some non-linearity
    # some cases cannot be solved by ordering alone, needs non-linearity
    # should cope with unknown orientation
    def can_add(self,scaled)->bool:
        'checks only tail_overlap'
        if not self.stack:
            return True

        tail=data.Oligo.can_tail_overlap
        # for each peak in scaled
        # find the corresponding peak from self.ordered
        for peak in scaled.arr:
            key=self.assign_key(peak)
            if key is not None:
                if not tail(self.stack[key][-1].seq,
                            peak.seq,
                            self.min_overlap,
                            oriented=False,
                            shift=1):
                    return False
        return True

    def assign_key(self,peak:data.Oligo)->float:
        'find which stack must be incremented by peak'
        comp=numpy.array(sorted(self.stack.keys()))-peak.pos
        try:
            return numpy.array(sorted(self.stack.keys()))[comp<=0][-1]
        except IndexError:
            return None

    # check implementation of reversing sequence to match top of stack
    def _add2stack(self,scaled:OPeakArray)->None:
        'adds a new peakarray to the stack'
        if not self.stack:
            self.stack={peak.pos:[peak] for peak in self.ordered[0].arr}
            return
        for peak in scaled.arr:
            key=self.assign_key(peak)
            if key is not None:
                last=self.stack[self.assign_key(peak)][-1]
                if data.Oligo.tail_overlap(last.seq,peak.seq):
                    self.stack[self.assign_key(peak)].append(peak)
                else:
                    self.stack[self.assign_key(peak)].append(peak.reverse(in_place=False))
            else:
                self.stack[peak.pos]=[peak]

    def top(self)->OPeakArray:
        '''
        returns a PeakArray where each peak is the top of each stack
        In the general case contains peaks with different sequences
        '''
        return OPeakArray(arr=numpy.array([val[-1] for val in self.stack.values()]))

    # should include non-linearity in this method
    def add(self,scaled:OPeakArray,in_place=True):
        'adds a scaled peakarray'
        # must check can_add prior to adding
        if in_place:
            self.ordered.append(scaled)
            self._add2stack(scaled)
            return
        cpy=self.copy()
        cpy.ordered.append(scaled)
        cpy._add2stack(scaled) # pylint: disable=protected-access
        return cpy

    def stack_oligos(self):
        'returns private ooligos'
        return [data.stack_sequences(*val) for key,val in self.stack.items()]

    def last(self):
        'returns last scaled OPeakArray'
        return self.ordered[-1]

    def reverse(self,key):
        'takes the reverse complement of all peaks at position key'
        for peak in self.stack[key]:
            peak.reverse()

    def __copy__(self):
        return type(self)(ordered=self.__dict__.get("ordered",[]))

    def copy(self):
        'returns copy'
        return self.__copy__()

class Scaler:
    '''
    varies stretch and bias between Oligo Experiments
    '''
    bp2nm=BP2NM # type: float
    nl_amplitude=5*bp2nm # type: float # in nm
    oligos=[] # type: List[data.OligoPeak]
    peaks=[] # type: List[data.OPeakArray]
    min_overlap=2 # type: int # need to rethink this parameter and its interaction
    with_reverse=True # type: bool
    bstretch=Bounds() # type: Bounds
    bbias=Bounds() # type: Bounds
    ref_index=0 # type: int # index of the reference OPeakArray
    shuffler=shuffler.Shuffler()
    pstack=PeakStack()
    @initdefaults(frozenset(locals()))
    def __init__(self,**kwa):
        pass

    def filterleftoverlap(self,peaks1,peaks2):
        'returns True if any in (peak1,peak2) tail_overlap'
        __rev=data.Oligo.reverse_complement
        seqs1=frozenset(i.seq for i in peaks1.arr)
        seqs2=frozenset(i.seq for i in peaks2.arr)
        seqs2=seqs2.union(frozenset(__rev(i.seq) for i in peaks2.arr))
        for seq1,seq2 in itertools.product(seqs1,seqs2):
            if len(data.OligoPeak.tail_overlap(seq1,seq2))>=self.min_overlap:
                return True

        return False


    # to rename as build_stacks
    def build_stacks_fromtuple(self,
                               stack:PeakStack,
                               peakarrs)->List[PeakStack]:
        '''
        use itertools.permutations(peaks,4) to feed tuples
        '''

        if not peakarrs:
            return [stack]

        refpeak=stack.top()
        def cmpfilter(peak):
            'filter'
            return self.filterleftoverlap(refpeak,peak)

        stacks=[] # type: List[PeakStack]
        scperpeak=self.find_rescales(refpeak,[peakarrs[0]],tocmpfilter=cmpfilter)
        for idx,val in scperpeak.items():
            print(f"idx={idx}")
            print(f"val={val}")

        toadd=[(peak,scale) for peak,scales in scperpeak.items()
               for scale in scales if stack.can_add(scale(peak))]
        print(f"len(toadd)={len(toadd)}")

        for peak,scale in toadd:
            print(f"scale={scale}")
            stacks+=self.build_stacks_fromtuple(stack=stack.add(scale(peak),in_place=False),
                                                peakarrs=peakarrs[1:])
            print(f"len(stacks)={len(stacks)}")

        return stacks


    def build_stacks(self,
                     stack:PeakStack,
                     peakarrs:FrozenSet[OPeakArray])->List[PeakStack]:
        '''
        recursive
        '''

        if not peakarrs:
            return [stack]

        refpeak=stack.top()
        def cmpfilter(peak):
            'filter'
            return self.filterleftoverlap(refpeak,peak)

        scperpeak=self.find_rescales(refpeak,peakarrs,tocmpfilter=cmpfilter)
        toadd=[(peak,scale) for peak,scales in scperpeak.items() for scale in scales
               if stack.can_add(scale(peak))]
        if not toadd:
            return [stack]

        stacks=[] # type: List[PeakStack]
        for peak,scale in toadd:
            stacks+=self.build_stacks(stack=stack.add(scale(peak),in_place=False),
                                      peakarrs=peakarrs-frozenset([peak]))
        return stacks


    def _increment_stack(self,
                         stack:PeakStack,
                         peakarrs:FrozenSet[OPeakArray])->List[PeakStack]:
        '''
        recursive
        '''

        if not peakarrs:
            return [stack]

        refpeak=stack.top()
        def cmpfilter(peak):
            'filter'
            return self.filterleftoverlap(refpeak,peak)

        scperpeak=self.find_rescales(refpeak,peakarrs,tocmpfilter=cmpfilter)
        toadd=[(peak,scale) for peak,scales in scperpeak.items() for scale in scales
               if stack.can_add(scale(peak))]

        if not toadd:
            return [stack]

        return [stack.add(scale(peak),in_place=False) for peak,scale in toadd]

    # wrong, still infinite loop (need to tag peaks already added)
    def new_build_stacks(self,
                         stack:PeakStack,
                         peakarrs:FrozenSet[OPeakArray])->List[PeakStack]:
        '''
        add any possible peakarrs one at a time
        if any is not possible then we have considered the wrong combination
        '''
        stacks=self._increment_stack(stack,peakarrs)
        for ite in range(3): # len(peakarrs)): # pylint: disable=unused-variable
            print(f"ite={ite}")
            max_size=max(len(stck.ordered) for stck in stacks)
            print(f"max_size={max_size}")
            print(f"len(stacks)={len(stacks)}")
            new_stacks=[] # type: List[PeakStack]
            for stck in stacks:
                new_stacks+=self._increment_stack(stck,peakarrs)

            stacks=new_stacks
        return stacks

    def run(self):
        '''
        ## ORIGINAL PLAN, TOO LONG TO RUN
        # take the 2 peaks in refpeak which are the more closely related
        # find all possible combination of rescaled peaks which fills the gap between these peaks
        # shuffle these peaks and keep the best order
        # these peaks now belong the same batch (cannot switch orders)
        # -> fewer permutations to consider
        # restart with the next unfilled gap between peaks of refpeak
        # we can pick (arbitrarily the seq or its reverse complement of the first peak in refpeak)

        ## alternate plan:
        *pick a reference peakarray, refpeak
        *must not consider reverse_complement of oligos in refpeak:
        reduces computation, can reverse seq of some peaks in refpeak to lift incoherency
        *find peakarray-refpeak which may overlap with refpeak
        *for each overlapping peakarray find the scale(stretch+bias)
        *for each scaled peakarray to an object (Scaffold):
        a Scaffold can only contain 1 copy of a peakarray (modulo scale)
        '''
        exp_oligos=no_orientation(self.oligos) # type: List[data.OligoPeak]
        self.peaks=OPeakArray.from_oligos(exp_oligos) # type: List[data.OPeakArray]
        self.peaks=sorted(self.peaks,key=lambda x:-len(x.arr))
        refpeak=self.peaks[self.ref_index]

        self.pstack.add(refpeak)

        # build_stacks

        stacks=self.build_stacks(self.pstack,frozenset(self.peaks[1:]))


        # for iteration in range(3):
        #     print(f"iteration={iteration}")
        # add next peak to the stack
        # trying to reduced the numbers of possible stacks
        # by fixing the sequences will only work when we hit a cycle


        # ref oligos is A then add Bs (B1,B2,B3) and see if there is some conflict between
        # events at different peaks
        # resolve conflicts if possible
        # could use shuffler at a later stage to readjust locally some events

        # Must take into account
        # * the minimal distance between 2 overlapping oligos
        # * the boundaries of the bucket are not allowed to be permutated
        # (shuffle relative to boundaries)
        # we can attempt to reorder events in bucket by looking at the possible sequences


        return refpeak,stacks

    def find_rescales(self,refpeak:OPeakArray,others:Iterable[OPeakArray],tocmpfilter=None):
        '''
        for each other peak, find all possible rescales (stretch and bias)
        matching filter is a function taking refpeak and others:List[OPeakArray]
        filter
        '''
        torescale=others
        if tocmpfilter:
            torescale=frozenset(filter(tocmpfilter,others))

        rescaleperpeak=dict() # type: Dict[OPeakArray,List]
        for peak in torescale:
            scales=refpeak.find_matches(peak,self.bstretch,self.bbias,self.with_reverse)
            if not scales:
                continue
            rescaleperpeak[peak]=scales

        return rescaleperpeak

# must take into account the 2 strands of the hairpin as soon  as possible in the program

# how to deal effectively with reverse_complement and overlapping? for example with
# aat whose reverse complement is att, aat and aat may overlap
# in any case we can't adjust the stretch, bias in this case to match the oligo
# consider individual peaks, each can be one sequence or its reverse complement
