#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# must correct basewise module to account for any sensible type of data
'''
variables to consider:
	  *bias (per oligo exp) (a)
	  *non linearity (b) (+- 10 bases, rough estimate, lets make it 15)
           can be used when determining if 2 oligos overlap or not
	  *stretch (small variations of the size of the hairpin between oligo exp) (c)


pos in (micrometer)=(pos in base number-bias)/stretch

we wish to maximize the correspondance of peaks:
   corresponding to overlapping sequences,
   AND given boundaries on stretch and bias:
c_i*o_i+a_i
where o_i is the array of position of oligo_i peaks in micrometer
o_i=array(peakj+b_j for j in exp)


TP: True Positive
FP: False Positive
FN: False Negative

Notes:
(1)we can still run the algorithm using a subset of oligos
for example oligo i with all oligos which can overlap with i
(2)we can push this further: select one oligo peak (detected event), i,
and (some, the number can be discussed in (3) ) other peaks
which corresponding to oligos with overlapping sequences
and satisfy stretch and bias boundaries. then run the basewise algorithm
ultimately we could create statistics on the probability of the peak being
True positive, False Positive, False Negative
(3)we can either consider a single cluster of overlapping peaks:
- 2 overlapping peaks but that would be useless because we know they overlap (by sequence)
(4)we can consider N-different clusters of P overlapping peaks
(a priori 2 different cluster are not designed to overlap):
- if P=2, we can easily compute the stretch-bias which
maximises overlapping peaks without using the basewise algorithm.
here the non-linearity is a variable which act as a valve.
For a given oligo sequence we can test (and rank (according to
noverlaps? no... we test 2 oligo experiments whose sequence overlap,
we can rank by matched peak)) all possible solutions for P=2.
if we do that for every pair of overlapping oligos, we can start
making statistics on the probability of a peak being (TP or FP)
for example if we have 1 peak which  never "meets" a complementary
sequence, we can assume it is a FP
- for P=3, we can make guesses whether we have False Negatives for the "middle" oligo
example: ATT, TTG, TGA. If we have ATT and TGA matching but no
detected events of TTG then there is a proba 0.25 that
TTG is the missing peak (TAG, TCG, TGG are the other possibilities)
- actually TAG, TCG & TGG would all have the same probability
except if we have more info from reverse_complement experiments
- it is more difficult to guesstimate more complex scenarios with 3-mers and P>=4
'''

import itertools
from typing import List, Tuple # pylint:disable=unused-import
import numpy
from utils import initdefaults
import assemble.data as data

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

class Scale:
    'groups stretch and bias values'
    def __init__(self,stretch,bias):
        self.stre=stretch
        self.bias=bias
    def __call__(self,array):
        return self.stre*array+self.bias


def match_peaks(peaks1,
                peaks2,
                bound_stretch:Bounds,
                bound_bias:Bounds)->List[Scale]:
    '''
    NEEDS TO ACCOUNT FOR PRECISION (not yet implemented,
    missing cases where bounds would discard solutions but not bounds+precision)
    if peakcalling wan take account of precision, consider peakcalling as a better alternative
    peaks1 is supposed fixed
    returns stretches and biases
    '''
    scales=[]
    # find all biases with at least 1 match
    # for all biases add all stretch values such that another match is created
    biases=[]
    for pe1 in peaks1:
        for pe2 in peaks2:
            if bound_bias.nisin(pe1-pe2):
                continue
            scales.append(Scale(1,pe1-pe2))
            biases.append(pe1-pe2)
            #stretches.append(1)

    for bias in list(biases):
        for p11,p12 in itertools.combinations(peaks1,2):
            for p21,p22 in itertools.combinations(peaks2,2):
                stretch=(p12-p11)/(p22-p21)
                if bound_stretch.nisin(stretch):
                    continue
                if count_matches(peaks1,stretch*peaks2+bias)>0:
                    #stretches.append(stretch)
                    #biases.append(bias)
                    scales.append(Scale(stretch,bias))

    return scales

def count_matches(peaks1,peaks2,fprecision=1e-3):
    '''
    peaks1 and peaks2 are 2 scaled arrays
    this function is asymmetric!
    need to be cautious.
    Cannot use this method to rank matching OPeakArray and use the fprecision
    to account for non-linearity (has valve to fitting)
    '''
    count=0
    for peak in peaks2: # reverse role of peak1 and peak2??
        if numpy.isclose(peaks1,peak,atol=fprecision).any():
            count+=1
    return count

class OPeakArray:
    '''
    corresponds to an experiment with a single oligo
    reconsider this as an array of OligoPeak
    each OligoPeak can be either sequence or reverse complement sequence
    Can even include Oligo experiments with different (not reverse_complement) sequences
    '''
    arr=numpy.empty(shape=(0,),dtype=data.OligoPeak)
    min_overl=1 # type: int
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

    def match_to(self,other,bstretch,bbias,with_reverse=True)->List:
        '''
        needs to take into account the seq of matching OligoPeaks
        stretches,biases are defined using self has (1,0)
        includes reverse_complement
        '''
        sseqs=frozenset(oli.seq for oli in self.arr)
        oseqs=frozenset(oli.seq for oli in other.arr)
        if with_reverse:
            sseqs=sseqs.union(frozenset(self.rev(oli.seq) for oli in self.arr))
            oseqs=oseqs.union(frozenset(other.rev(oli.seq) for oli in other.arr))

        matches=[(str1,str2)
                 for str1 in sseqs
                 for str2 in oseqs
                 if len(data.Oligo.tail_overlap(str1,str2))>self.min_overl]
        print("matches=",matches)
        scales=[] # type: List[Scale]
        for match in matches:
            arr1=self.matching_seq(match[0])
            arr2=other.matching_seq(match[1])
            #stretch,bias
            scales+=match_peaks(arr1,
                                arr2,
                                bstretch,
                                bbias)
        return scales

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

    def count_matches(self,scaled): #->int:
        '''
        maximum number of matches in self.peak
        '''
        pass

def no_orientation(oligos:List[data.OligoPeak]):
    'each oligo has its sequence changed so that we loose the information on the orientation'
    reverse=data.Oligo.reverse_complement
    return [data.OligoPeak(seq=min(oli.seq,reverse(oli.seq)),pos=oli.pos)
            for oli in oligos]




class Scaler:
    '''
    varies stretch and bias between Oligo Experiments
    '''
    oligos=[] # type: List[data.OligoPeak]
    peaks=[] # type: List[data.OPeakArray]
    bp2nm=1.1 # type: float
    nl_amplitude=15*bp2nm # type: float # in nm
    min_overlap=1 # type: int
    with_reverse=True # type: bool
    bstretch=Bounds()
    bbias=Bounds()
    @initdefaults(frozenset(locals()))
    def __init__(self,**kwa):
        pass

    def run(self):
        '''
        assemble the sequence using basewise for small, local adjustments of OligoPeak
        and varying stretch and bias between peaks

        pick the first peakarray (also the largest) (peakarray1)
        find all other arrays which may overlap
        for each array to add, find all stretch and bias
        for each stretch and bias, apply basewise to each cluster of peaks
        to define a cluster start with a peak in peaks1,
        the cluster is define as all peaks matching this peak
        because all OligoPeak which may overlap (in sequence (min_overl=1?)
        AND in distance using nl_amplitude)
        with any given peak in peaks1 are considered, we can define
        a quality score for each peak in peakarray1
        we can then compute the quality score of another
        peakarray (whose sequence overlap with 2 with peakarray1)
        '''
        exp_oligos=no_orientation(self.oligos) # type: List[data.OligoPeak]
        self.peaks=OPeakArray.from_oligos(exp_oligos) # type: List[data.OPeakArray]
        self.peaks=sorted(self.peaks,key=lambda x:-len(x.arr))
        peakarr0=self.peaks[0]
        toscale=OPeakArray.may_overlap(peakarr0,self.peaks[1:],self.min_overlap,self.with_reverse)
        scaleperpeak={peak:peakarr0.match_to(peak,self.bstretch,self.bbias,self.with_reverse)
                      for peak in toscale}
        scaleperpeak={k:v for k,v in scaleperpeak.items() if len(v)>0}
        # find the combinaison of scales for each of the peaks matched peakarr0
        # per peak rank the scales according to matches
        # we can merge OligoPeaks if we can identify the overlapping
        # OligoPeaks (saves time with basewise)

        return scaleperpeak


# must take into account the 2 strands of the hairpin as soon  as possible in the program
#oligos=pickle.load(open("oligos_sd1_os3.pickle","rb"))

# more difficult to start analysis of peaks if only 1 is detected (FP? TP? etc..)

# how to deal effectiveley with reverse_complement and overlapping? for example with
# aat whose reverse complement is att,  aat and aat may overlap
# in any case we can't adjust the stretch, bias  in this case to match the oligo
# consider individual peaks, each can be one sequence or its reverse complement
