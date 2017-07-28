#!/usr/bin/env python3
# -*- coding: utf-8 -*-

'''
non-linearity not implemented (for each OPeakArray)

should deal with any orientation (keeps possible stacks depending if no conflict)
'''

import itertools
from typing import List, Tuple, Dict, FrozenSet, Iterable, Generator # pylint:disable=unused-import
import numpy
import networkx
from utils import initdefaults
import assemble.data as data
import assemble.shuffler as shuffler

BP2NM=1.1

# to finish
def stack_paths(graph:networkx.DiGraph,
                source=None)->Generator:
    '''
    works for directed graphs
    combine cyclic paths
    '''

    circuit=list(networkx.eulerian_circuit(graph,source=source))
    path=[val[0] for val in circuit]
    spath=tuple(val for idx,val in enumerate(path)
                if path.index(val)==idx
                or val==source)
    yield spath

# probably not going to be used
def hamiltonian_paths(graph:networkx.Graph,
                      source=None)->Generator:
    '''
    returns paths for which each node is visited once
    works in the special case where the graph in undirected
    yields nothing if the (graph,source) does not allow hamiltonian path
    brute force
    '''
    if source is None:
        source=graph.nodes()[0]

    paths=networkx.all_simple_paths(graph,source=source,target=source)
    for path in paths:
        if len(frozenset(path))==len(graph):
            yield path

def cyclic_paths(graph:networkx.Graph,
                 source=None)->Generator:
    '''
    yields all paths starting and ending at source
    '''
    if not graph:
        return []

    start=source
    if start is None:
        start=graph.nodes()[0]

    paths=networkx.all_simple_paths(graph,
                                    source=start,
                                    target=start,
                                    cutoff=len(graph))
    for path in paths:
        yield path

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

    if __debug__:
        print(f"biases={biases}")
    for bias in list(biases):
        for pe2 in peaks2:
            if numpy.isclose(pe2,0):
                continue
            upper=peaks1>=bound_stretch.lower*pe2+bias
            lower=peaks1<=bound_stretch.upper*pe2+bias
            tostretch=numpy.array(peaks1)[numpy.logical_and(upper,lower)]
            for stre in tostretch:
                # if __debug__:
                #     print(f"stre={stre}")
                #     print(f"bias={bias}")
                #     print(f"pe2={pe2}")

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
        includes reverse_complement of other
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
        return tuple(i.seq for i in self.arr)

    @staticmethod
    def may_overlap(peak,others:Iterable,min_overl:int,with_reverse=True)->List:
        '''
        compare the sequences of the 2 experiments
        returns True if the 2 sequences may overlap
        False otherwise
        if with_reverse, also considers reverse_complement of others
        '''
        to_match=frozenset(i.seq for i in peak.arr)
        match=[]
        for seq in to_match:
            for opk in others:
                for tocheck in opk.seqs:
                    if data.Oligo.can_tail_overlap(seq,tocheck,min_overl,not with_reverse,shift=1):
                        match.append(opk)
                        break
        return match

    @staticmethod
    def list2graph(peaks:List,min_overl=2):
        '''
        peaks is a list of OPeakArrays
        returns the full directed graph
        needed for Hamiltonian path
        '''
        graph=networkx.DiGraph()
        for peak in peaks:
            toadd=OPeakArray.may_overlap(peak,
                                         frozenset(peaks)-frozenset([peak]),
                                         min_overl=min_overl)
            graph.add_edges_from([(peak,other) for other in toadd])
        return graph


    @staticmethod
    def list2tree(refpeak,
                  others:Iterable,
                  min_overl=2,
                  depth=4):
        '''
        use networkx to reconstruct all possible paths
        returns the graph, and the tips of the tree (from all_simple_paths search)
        '''
        others=frozenset(others)
        graph=networkx.DiGraph()
        last_added=frozenset([refpeak])
        for layer in range(depth):
            print(f"layer,depth={layer},{depth}")
            others=others-last_added
            print(f"len(others)={len(others)}")
            alladded=[] # type: List
            for newroot in last_added:
                toadd=OPeakArray.may_overlap(newroot,others,min_overl)
                print(f"len(toadd)={len(toadd)}")
                graph.add_edges_from([(newroot,add) for add in toadd])
                alladded+=toadd

            last_added=frozenset(alladded)

        return graph,list(last_added)

    def __hash__(self)->int:
        '''
        simple hash considering only sequences
        '''
        return hash(self.seqs)

    def __eq__(self,other)->bool:
        '''
        2 are equivalent if invariant under scaling (stretch,bias)
        '''
        if isinstance(other,type(self))\
        and hash(self)==hash(other)\
        and len(self.posarr)==len(other.posarr):
            if len(self.posarr)==1:
                return True
            sarr=self.posarr
            oarr=other.posarr
            sarr=(sarr-sarr[0])/max(abs(sarr-sarr[0]))
            oarr=(oarr-oarr[0])/max(abs(oarr-oarr[0]))
            return all(numpy.isclose(sarr,oarr))
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
        self.min_overl=kwa.get("min_overl",2) # type: int
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
                            self.min_overl,
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
    def _add2stack(self,peakarray:OPeakArray)->None:
        'adds a new (scaled or unscaled? scaled!) peakarray to the stack'
        if not self.stack:
            self.stack={peak.pos:[peak] for peak in self.ordered[0].arr}
            return
        # check if multiple peaks are assigned to the same key
        # if yes, add keys

        assigned=[] # type: List[Tuple]
        for peak in peakarray.arr:
            key=self.assign_key(peak)
            assigned+=[(str(key),peak.pos,key,peak)]
        assigned=sorted(assigned,
                        key=lambda x:tuple(x[:2]))

        for key,group in itertools.groupby(assigned,key=lambda x:x[2]):
            if key is None:
                for grp in group: # not necessarily of size 0 or 1
                    self.stack[grp[1]]=[grp[3]]
            else:
                tostack=list(group)
                key,peak=tostack[0][2:]
                last=self.stack[key][-1]
                if data.Oligo.tail_overlap(last.seq,peak.seq):
                    self.stack[key].append(peak)
                else:
                    self.stack[key].append(peak.reverse(in_place=False))
                for grp in tostack[1:]:
                    self.stack[grp[1]]=[grp[3]]

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

    def reverse(self,key=None):
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
    min_overl=2 # type: int # need to rethink this parameter and its interaction
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
            if len(data.OligoPeak.tail_overlap(seq1,seq2))>=self.min_overl:
                return True

        return False


    def build_stack_fromtuple(self,
                              stack:PeakStack,
                              peakarrs)->List[PeakStack]:
        '''
        peakarrs is a list of unscaled OPeakArray objects
        '''

        if not peakarrs:
            return [stack]

        refpeak=stack.top()
        def cmpfilter(peak):
            'filter'
            return self.filterleftoverlap(refpeak,peak)

        stacks=[] # type: List[PeakStack]
        scperpeak=self.find_rescales(refpeak,[peakarrs[0]],tocmpfilter=cmpfilter)

        toadd=[(peak,scale) for peak,scales in scperpeak.items()
               for scale in scales if stack.can_add(scale(peak))]
        print(f"len(toadd)={len(toadd)}")
        for peak,scale in toadd:
            stacks+=self.build_stack_fromtuple(stack=stack.add(scale(peak),in_place=False),
                                               peakarrs=peakarrs[1:])

        return stacks


    def build_stack(self,
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
            stacks+=self.build_stack(stack=stack.add(scale(peak),in_place=False),
                                     peakarrs=peakarrs-frozenset([peak]))
        return stacks

    def incr_build(self,stack:PeakStack)->List[PeakStack]:
        '''
        build incrementally the stacks depth OPeakArrays at a time
        returns the incremented stacks
        '''
        addstacks=[] # type: List[PeakStack]
        others=frozenset(self.peaks)-frozenset(stack.ordered)
        graph,tips=OPeakArray.list2tree(stack.top(),others,min_overl=self.min_overl,depth=1)
        paths=[] # type: List[OPeakArray]
        for tip in tips:
            paths+=[path[1:]
                    for path in networkx.all_simple_paths(graph,source=stack.top(),target=tip)]
        for path in paths:
            addstacks=self.build_stack_fromtuple(stack,path)
        return addstacks

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
        # exp_oligos=no_orientation(self.oligos) # type: List[data.OligoPeak] # keep for later
        exp_oligos=list(self.oligos)
        self.peaks=OPeakArray.from_oligos(exp_oligos) # type: List[data.OPeakArray]
        self.peaks=sorted(self.peaks,key=lambda x:-len(x.arr))
        refpeak=self.peaks[self.ref_index]
        pstack=PeakStack()
        pstack.add(refpeak)

        peakset=frozenset(self.peaks)

        pstacks=[pstack]
        # quick and dirty solution for accounting for different starting sequences.
        # duplicate them (any combination for arr in peaks[0])
        # or add it when looking for overlaps

        # building_stacks
        # infinite loop to fix
        while any(peakset-frozenset(stack.ordered) for stack in pstacks):
            new_stacks=[] # type: List[PeakStack]
            for stack in pstacks:
                if peakset-frozenset(stack.ordered):
                    new_stacks+=self.incr_build(stack)
                else:
                    new_stacks.append(stack)
            pstacks=new_stacks
            if __debug__:
                print(f"len(pstacks)={len(pstacks)}")

        return pstacks

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
            print(f"peak={peak.posarr}")
            scales=refpeak.find_matches(peak,self.bstretch,self.bbias,self.with_reverse)
            if not scales:
                continue
            rescaleperpeak[peak]=scales

        return rescaleperpeak

# how to deal effectively with reverse_complement and overlapping? for example with
# aat whose reverse complement is att, aat and aat may overlap
# in any case we can't adjust the stretch, bias in this case to match the oligo
# consider individual peaks, each can be one sequence or its reverse complement
