#!/usr/bin/env python3
# -*- coding: utf-8 -*-

'''
non-linearity not implemented (for each OPeakArray)
'''
import abc
import itertools
from typing import List, Tuple, Dict, FrozenSet, Iterable, Generator # pylint:disable=unused-import
import numpy as np
import networkx
from utils import initdefaults
import assemble.data as data

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

    # too long. create peakarray?
    def __call__(self,array):
        return self.stre*array+self.bias

    def __str__(self):
        return f'({self.stre},{self.bias})'

    @property
    def toarr(self):
        'array of stre,bias'
        return np.array([self.stre,self.bias])

    def __hash__(self):
        return hash((self.stre,self.bias))

    def __eq__(self,other):
        if isinstance(other,type(self)):
            return all(np.isclose(self.toarr,other.toarr,atol=self.atol))
        return False

def scale_peaks(peaks1:np.array,
                peaks2:np.array,
                bstretch:Bounds,
                bbias:Bounds)->List[Rescale]:
    'uses macth_peaks but return Rescale objects'
    return [Rescale(stre,bias)
            for stre, bias in match_peaks(peaks1,
                                          peaks2,
                                          bstretch,
                                          bbias)]

def match_peaks(peaks1:np.array,
                peaks2:np.array,
                bstretch:Bounds,
                bbias:Bounds)->List[Tuple[float,float]]:
    '''
    NEEDS TO ACCOUNT FOR PRECISION (not yet implemented,
    missing cases where bounds would discard solutions but not bounds+precision)
    if peakcalling wan take account of precision, consider peakcalling as a better alternative
    peaks1 is supposed fixed
    returns stretches and biases

    # for each index in peaks2:
    # find indices from peaks1 that are > bstretch.min*peaks2
    # and indices from peaks1 that are < bstretch.max*peaks2
    # start with lowest stretch to max stretch

    '''
    scales=[]
    # find all biases with at least 1 match
    # for all biases add all stretch values such that another match is created
    biases=[]
    for pe1 in peaks1:
        for pe2 in peaks2:
            if bbias.nisin(pe1-pe2):
                continue
            scales.append((1,pe1-pe2))
            biases.append(pe1-pe2)

    # for bias in list(biases):
    for bias in biases:
        for pe2 in peaks2:
            # if np.isclose(pe2,0):
            #     continue
            if not pe2:
                continue
            upper=peaks1>=bstretch.lower*pe2+bias
            lower=peaks1<=bstretch.upper*pe2+bias
            # apply -bias/pe2 to tostretch
            tostre=(np.array(peaks1)[np.logical_and(upper,lower)]-bias)/pe2
            scales.extend([(stre,bias) for stre in tostre])

    return list(frozenset(scales))

def count_matches(peaks1,peaks2,fprecision=1e-3):
    '''
    peaks1 and peaks2 are 2 scaled arrays
    this function is asymmetric!
    '''
    count=0
    for peak in peaks1:
        if np.isclose(peak,peaks2,atol=fprecision).any():
            count+=1
    return count

# move to data.py
class OPeakArray:
    '''
    corresponds to an experiment with a single oligo
    each OligoPeak can be either sequence or reverse complement sequence
    Can even include Oligo experiments with different (not reverse_complement) sequences
    '''
    arr=np.empty(shape=(0,),dtype=data.OligoPeak)
    min_overl=2 # type: int
    rev=data.Oligo.reverse_complement
    uniqueid=-1 # type: int # allows to differentiate single peaks
    @initdefaults(frozenset(locals()))
    def __init__(self,**kwa):
        pass

    @staticmethod
    def from_oligos(oligos:List[data.OligoPeak],**kwa)->List:
        'return Peaks from oligos'
        solis=sorted([(oli.seq,oli.pos,oli) for oli in oligos])
        exp=[]
        for values in itertools.groupby(solis,key=lambda x:x[0]):
            exp.append(OPeakArray(arr=np.array([oli[2] for oli in values[1]])))
        if kwa.get("sorted",True):
            return sorted(exp,key=lambda val: -len(val))
        return exp

    def matching_seq(self,seq,unsigned=True):
        '''returns the array of position which match seq'''
        if unsigned:
            return np.array([i.pos for i in self.arr if i.seq==seq or self.rev(i.seq)==seq])
        return np.array([i.pos for i in self.arr if i.seq==seq])

    def find_matches(self,other,bstretch,bbias,unsigned=True)->List[Rescale]:
        '''
        needs to take into account the seq of matching OligoPeaks
        stretches,biases are defined using self has (1,0)
        includes reverse_complement of other
        '''
        sseqs=frozenset(oli.seq for oli in self.arr)
        oseqs=frozenset(oli.seq for oli in other.arr)
        if unsigned:
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
            scales+=scale_peaks(arr1,
                                arr2,
                                bstretch,
                                bbias)
        return list(frozenset(scales))

    @property
    def posarr(self):
        'array of oligo positions'
        return np.array([oli.pos for oli in self.arr])

    @posarr.setter
    def posarr(self,values:np.array):
        'changes the pos of oligos within the peakarr'
        for idx,val in enumerate(values):
            self.arr[idx].pos=val

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
    def may_overlap(peak,others:Iterable,min_overl:int,unsigned=True)->List:
        '''
        compare the sequences of the 2 experiments
        returns True if the 2 sequences may overlap
        False otherwise
        if unsigned, also considers reverse_complement of others
        '''
        to_match=frozenset(i.seq for i in peak.arr)
        match=[]
        for seq in to_match:
            for opk in others:
                for tocheck in opk.seqs:
                    if data.Oligo.can_tail_overlap(seq,tocheck,min_overl,not unsigned,shift=1):
                        match.append(opk)
                        break
        return match

    @classmethod
    def list2edgeids(cls,
                     peaks:List,
                     min_overl:int=2,
                     unsigned=True):
        '''
        returns the edges of peak indices which overlap
        '''
        edges=[(idx1,idx2) for idx1,idx2 in itertools.permutations(range(len(peaks)),2)
               if cls.may_overlap(peaks[idx1],
                                  [peaks[idx2]],
                                  min_overl=min_overl,unsigned=unsigned)]
        return sorted(edges)

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

    # to improve
    # creates duplicates because it allows tips to be added
    # for each of those added tips, if they don't really do overlap
    # then they create duplicates since stack_fromtuple returns stack
    # if no peak array are added to the stack
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
        for _ in range(depth):
            others=others-last_added
            alladded=[] # type: List
            for newroot in last_added:
                toadd=OPeakArray.may_overlap(newroot,others,min_overl)
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

        if not isinstance(other,type(self)):
            return False

        if hash(self)==hash(other)\
           and len(self.posarr)==len(other.posarr):
            if len(self.posarr)==1:
                return self.uniqueid==other.uniqueid # to change probably
            sarr=self.posarr
            oarr=other.posarr
            sarr=(sarr-sarr[0])/max(abs(sarr-sarr[0]))
            oarr=(oarr-oarr[0])/max(abs(oarr-oarr[0]))
            return all(np.isclose(sarr,oarr))
        return False


    def __copy__(self):
        'creates a copy'
        return type(self)(arr=np.array([oli.copy() for oli in self.arr]),
                          min_overl=self.min_overl,
                          rev=self.rev)
    def copy(self):
        'calls __copy__'
        return self.__copy__()

    def minseq(self,in_place=True):
        'sets the seq to the min sequence'
        if in_place:
            for oli in self.arr:
                if oli.seq!=min(oli.seq,data.Oligo.rev(oli.seq)):
                    oli.reverse()
            return
        cpy=self.copy()
        cpy.minseq()
        return cpy

    def reverse(self,in_place=True):
        'takes the reverse compelement of each oligos in the array'
        if in_place:
            for oli in self.arr:
                oli.reverse()
            return
        cpy=self.copy()
        cpy.reverse()
        return cpy

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
        self.stack=dict() # type: Dict[float,List[data.Oligo]]
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
                            signed=False,
                            shift=1):
                    return False
        return True

    def assign_key(self,peak:data.Oligo)->float:
        'find which stack must be incremented by peak'
        comp=np.array(self.keys)-peak.pos
        try:
            return np.array(self.keys)[comp<=0][-1]
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
                if len(data.Oligo.tail_overlap(last.seq,peak.seq))>=self.min_overl:
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
        return OPeakArray(arr=np.array([val[-1] for val in self.stack.values()]))

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

    def _add2keyonly(self,
                     key2add:float,
                     scaled:OPeakArray)->None:
        '''
        same as _add2stack must stack only to key
        other keys from scaled are added to self.stack
        '''
        if not self.stack:
            self.stack={peak.pos:[peak] for peak in self.ordered[0].arr}
            return

        assigned=[] # type: List[Tuple]
        for peak in scaled.arr:
            key=self.assign_key(peak)
            assigned+=[(str(key),peak.pos,key,peak)]
        assigned=sorted(assigned,
                        key=lambda x:tuple(x[:2]))

        for key,group in itertools.groupby(assigned,key=lambda x:x[2]):
            if key!=key2add:
                for grp in group:
                    self.stack[grp[1]]=[grp[3]]
            else:
                tostack=list(group)
                key,peak=tostack[0][2:]
                last=self.stack[key][-1]
                if len(data.Oligo.tail_overlap(last.seq,peak.seq))>=self.min_overl:
                    self.stack[key].append(peak)
                else:
                    self.stack[key].append(peak.reverse(in_place=False))
                for grp in tostack[1:]:
                    self.stack[grp[1]]=[grp[3]]

    def add2keyonly(self,
                    key:float,
                    scaled:OPeakArray,
                    in_place=True):
        'adds a scaled peakarray'
        # must check can_add prior to adding
        if in_place:
            self.ordered.append(scaled)
            self._add2keyonly(key,scaled) # to change
            return
        cpy=self.copy()
        cpy.ordered.append(scaled)
        cpy._add2keyonly(key,scaled) # pylint: disable=protected-access
        return cpy

    def stack_oligos(self):
        'returns private ooligos'
        return [data.stack_sequences(*val) for key,val in self.stack.items()]

    def last(self):
        'returns last scaled OPeakArray'
        return self.ordered[-1]

    def reverse(self,key=None):
        'takes the reverse complement of all peaks at position key'
        if key is None:
            for values in self.stack.values():
                for val in values:
                    val.reverse()
            return
        for peak in self.stack[key]:
            peak.reverse()

    @property
    def keys(self):
        'returns sorted keys'
        return sorted(self.stack.keys())

    def __keyseqs(self)->Tuple:
        'returns the keys and seqs of the values of self.stack'
        return tuple(sorted([(key,)+tuple([val.seq for val in values])
                             for key,values in self.stack.items()]))

    def __copy__(self):
        return type(self)(ordered=self.__dict__.get("ordered",[]))

    def copy(self):
        'returns copy'
        return self.__copy__()

    def __str__(self):
        to_str=""
        for key,values in self.stack.items():
            to_str+=f"{key} "+" ,".join(val.seq for val in values)+" \n"
        return to_str

    # rather long for an hash...
    def __hash__(self):
        return hash(tuple(self.ordered)+self.__keyseqs())

    def __eq__(self,other):
        if isinstance(other,type(self)) and hash(self)==hash(other):
            return True
        return False

class Scaler: # pylint: disable=too-many-instance-attributes
    '''
    varies stretch and bias between Oligo Experiments
    '''
    def __init__(self,**kwa):
        # self.bp2nm=BP2NM # type: float
        # self.nl_amplitude=5*bp2nm # type: float # in nm
        self.oligos=kwa.get("oligos",[]) # type: List[data.OligoPeak]
        self.min_overl=kwa.get("min_overl",2) # type: int # rethink this parameter
        # replace with_reverse by oriented (signed)
        #self.with_reverse=kwa.get("with_reverse",True) # type: bool
        self.unsigned=True # type: bool
        self.bstretch=kwa.get("bstretch",Bounds()) # type: Bounds
        self.bbias=kwa.get("bbias",Bounds()) # type: Bounds

        exp_oligos=no_orientation(self.oligos) # type: List[data.OligoPeak]
        #exp_oligos=list(self.oligos) # type: List[data.OligoPeak] # keep for testing
        self.peaks=OPeakArray.from_oligos(exp_oligos) # type: List[data.OPeakArray]
        self.peaks=sorted(self.peaks,key=lambda x:-len(x.arr))
        self.__peakset=frozenset(self.peaks) # type: FrozenSet[OPeakArray]
        self.pstack=PeakStack(min_overl=self.min_overl)
        self.pstack.add(self.peaks[kwa.get("ref_index",0)])

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

    def stack_fromtuple(self,
                        stack:PeakStack,
                        peakarrs)->List[PeakStack]:
        '''
        peakarrs is a list of unscaled OPeakArray objects
        similar to Scaler.stack_fromtuple but refpeak consist of a single Oligo event
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

        if not toadd: # check that this condition is correct
            return [stack]

        for peak,scale in toadd:
            stacks+=self.stack_fromtuple(stack=stack.add(scale(peak),in_place=False),
                                         peakarrs=peakarrs[1:])
        return stacks

    @abc.abstractmethod
    def stack_key_fromtuple(self,
                            key2add:float,
                            stack:PeakStack,
                            peakarrs)->List[PeakStack]:
        'abstract'

    # overkill to use networkx if we have trees of depth=2 (source+tip)
    # and time consuming to recreate trees...
    def incr_build(self,
                   stack:PeakStack,
                   key2fit=None)->List[PeakStack]:
        '''
        build incrementally the stacks depth OPeakArrays at a time
        returns the incremented stacks
        '''
        addstacks=[] # type: List[PeakStack]
        # need to compare the reverse too
        #others=self.__peakset-frozenset(stack.ordered)
        others=self.notin_stack(stack) # to check
        tips=OPeakArray.may_overlap(stack.top(),others,min_overl=self.min_overl) # to check

        if key2fit is None:
            for tip in tips:
                addstacks+=self.stack_fromtuple(stack,(tip,))
        else:
            for tip in tips:
                addstacks+=self.stack_key_fromtuple(key2fit,stack,(tip,))

        # graph,tips=OPeakArray.list2tree(stack.top(),others,min_overl=self.min_overl,depth=1)
        # for tip in tips:
        #     for path in networkx.all_simple_paths(graph,source=stack.top(),target=tip):
        #         if key2fit is None:
        #             addstacks+=self.stack_fromtuple(stack,path[1:])
        #         else:
        #             addstacks+=self.stack_key_fromtuple(key2fit,stack,path[1:])
        # if __debug__:
        #     print(f"len(addstacks)={len(addstacks)}")
        return addstacks

    def run(self,iteration=1)->List[PeakStack]:
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
        # refpeak=self.peaks[self.ref_index]
        # pstack=PeakStack(min_overl=self.min_overl)
        # pstack.add(refpeak)


        pstacks=[self.pstack]
        # quick and dirty solution for accounting for different starting sequences.
        # duplicate them (any combination for arr in peaks[0])
        # or add it when looking for overlaps

        # building_stacks

        return self.resume(pstacks,iteration=iteration)

    def resume(self,pstacks,iteration=1,try_concatenate:bool=False)->List[PeakStack]:
        '''
        resume, stacking (scaling) of stacks
        if self.incr_build(stack)==stack, stack is placed in a list of fixed stacks
        minor improvements on previous version
        '''
        fixed=frozenset([]) # type: FrozenSet[PeakStack]
        key2fit=getattr(self,"key2fit",None)
        for _ in range(iteration):
            if __debug__:
                print(f"iteration={_}")
                print(f'len(pstacks)={len(pstacks)}')
                print(f'fixed,pstacks={len(fixed),len(pstacks)}')
            new_stacks=[] # type: List[PeakStack]
            for stack in pstacks:
                toadd=frozenset(self.incr_build(stack,key2fit=key2fit))
                if stack in toadd:
                    new_stacks+=list(toadd - frozenset([stack]))
                    fixed=fixed.union([stack])
                else:
                    new_stacks+=toadd
            # if __debug__:
            #     print(f"len(fixed)={len(fixed)}")
            pstacks=frozenset(new_stacks)

            if try_concatenate and key2fit:
                fixed=fixed.union([self.can_concatenate(stk,key2fit,self.min_overl)
                                   for stk in new_stacks])

        return list(pstacks.union(fixed))

    # long
    def notin_stack(self,
                    stack:PeakStack)->FrozenSet[OPeakArray]:
        '''
        returns the set of OPeakArray which are in self.peaks
        but not in stack.ordered
        accounts for sign
        '''
        if self.unsigned:
            upeaks=frozenset([peak.minseq(in_place=False) for peak in stack.ordered])
            return frozenset([peak for peak in self.__peakset
                              if peak.minseq(in_place=False) not in upeaks])
        return self.__peakset-frozenset(stack.ordered)

    def find_rescales(self,refpeak:OPeakArray,others:Iterable[OPeakArray],tocmpfilter=None):
        '''
        for each other peak, find all possible rescales (stretch and bias)
        matching filter is a function taking refpeak and others:List[OPeakArray]
        eg self.filterleftoverlap(peaks1,peaks2) filter
        '''
        torescale=others
        if tocmpfilter:
            torescale=frozenset(filter(tocmpfilter,others))

        rescaleperpeak=dict() # type: Dict[OPeakArray,List]
        for peak in torescale:
            scales=refpeak.find_matches(peak,self.bstretch,self.bbias,self.unsigned)
            if not scales:
                continue
            rescaleperpeak[peak]=scales

        return rescaleperpeak

    @staticmethod
    def can_concatenate(stack:PeakStack,key:float,min_overl:int)->PeakStack:
        '''
        returns stack if keystack and next can overlap (unsigned)
        with next keystack
        otherwise returns []
        '''
        nextkey = stack.keys[np.argmax(np.array(stack.keys)>key)]
        first = stack.stack[nextkey][-1].seq
        second = stack.stack[nextkey][0].seq
        if data.Oligo.can_tail_overlap(first,second,min_overl,signed=False,shift=1):
            return stack
        return None

# needs a SubScaler class focusing on segments between two peaks
# find the best scales for peak array between these peaks (allow for a subselection of peaks)
# will be rewritten
class SubScaler(Scaler):
    '''
    Same as Scaler but focuses on the section between to peaks (event detected)
    to fix all the scales of oligos experiments which fall into this section
    trying to generate the stacks on the whole sequence at once is too intensive
    '''

    # needs oligos, peaks, min_overl
    # unsigned bstretch, bbias, ref_index

    def __init__(self,**kwa):
        super().__init__(**kwa)
        self.__posid=kwa.get("posid",0) # type: int # id of pstack.posarr
        self._key2fit=self.pstack.keys[self.__posid] # type: float

    @property
    def posid(self):
        'posid attribute'
        return self.__posid

    @posid.setter
    def posid(self,value):
        self.__posid=value
        self._key2fit=self.pstack.keys[self.__posid]

    @posid.getter
    def posid(self):
        'getter'
        return self.__posid

    def extract_key(self,stack:PeakStack)->OPeakArray:
        '''
        creates a OPeakArray consisting only of the Oligo event to match
        '''
        tomatch=stack.top().arr[np.abs(stack.top().posarr-self._key2fit).argmin()]
        return OPeakArray.from_oligos([tomatch])[0]

    def stack_fromtuple(self,
                        stack:PeakStack,
                        peakarrs)->List[PeakStack]:
        '''
        peakarrs is a list of unscaled OPeakArray objects
        similar to Scaler.stack_fromtuple but refpeak consist of a single Oligo event
        '''

        if not peakarrs:
            return [stack]

        refpeak=self.extract_key(stack)
        def cmpfilter(peak):
            'filter'
            return self.filterleftoverlap(refpeak,peak)

        stacks=[] # type: List[PeakStack]
        scperpeak=self.find_rescales(refpeak,[peakarrs[0]],tocmpfilter=cmpfilter)

        toadd=[(peak,scale) for peak,scales in scperpeak.items()
               for scale in scales if stack.can_add(scale(peak))]

        if not toadd: # check that this condition is correct
            return [stack]

        for peak,scale in toadd:
            stacks+=self.stack_fromtuple(stack=stack.add(scale(peak),in_place=False),
                                         peakarrs=peakarrs[1:])
        return stacks

    def stack_key_fromtuple(self,
                            key2add:float,
                            stack:PeakStack,
                            peakarrs)->List[PeakStack]:
        '''
        similar to stack_fromtuple except that a single key is stacked
        when adding a peakarray, one key is stacked to stack,
        the others are added to the stack
        '''
        if not peakarrs:
            return [stack]

        refpeak=self.extract_key(stack)
        def cmpfilter(peak):
            'filter'
            return self.filterleftoverlap(refpeak,peak)

        stacks=[] # type: List[PeakStack]
        scperpeak=self.find_rescales(refpeak,[peakarrs[0]],tocmpfilter=cmpfilter)
        toadd=[(peak,scale) for peak,scales in scperpeak.items()
               for scale in scales if stack.can_add(scale(peak))]
        # if __debug__:
        #     print(f"toadd={toadd}")
        #     print(f"scperpeak={scperpeak}")
        if not toadd:
            return [stack]

        for peak,scale in toadd:
            stacks+=self.stack_key_fromtuple(key2add,
                                             stack=stack.add2keyonly(key2add,
                                                                     scale(peak),
                                                                     in_place=False),
                                             peakarrs=peakarrs[1:])

        return stacks



    def test(self,try_concatenate:bool=True)->List[PeakStack]:
        '''
        this requires implementation and testing
        max number of peaks is 32
        must include only the add to stack only to the specified key.
        need to allow for reverse of keys
        how can we make so that it is an efficient search.
        We don't want to do the 2**40 combination for 40 peaks...
        * we need to start with the first orientation of the first peak.
        and reconstruct the sequences from there.
        * then consider the reverse of first peak
        and construct the other sequences from there
        * can need a score
        '''
        pstacks=[self.pstack]
        #for _ in range(len(self.pstack.keys)):
        #    print(f"posid={_}")
        #    self.posid=_
        self.posid=0
        pstacks=self.resume(pstacks,iteration=32,try_concatenate=try_concatenate)
        return pstacks

# how to deal effectively with reverse_complement and overlapping? for example with
# aat whose reverse complement is att, aat and aat may overlap
# in any case we can't adjust the stretch, bias in this case to match the oligo
# consider individual peaks, each can be one sequence or its reverse complement
