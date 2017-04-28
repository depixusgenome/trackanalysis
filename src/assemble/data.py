#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u'''
Creates Classes and function to use with assemble sequence
'''
from typing import List
from utils import initdefaults

class Oligo:
    u'''
    container for an oligo sequence, a position in nanometer
    and a position in base
    '''
    seq:str=""
    pos:int=-1
    bpos:int=-1 # base position
    @initdefaults
    def __init__(self,**kwa):
        pass
    @property
    def size(self):
        return len(self.seq)

    def overlap_with(self,other:Oligo):
        Oligo.__tail_overlap(self.seq,other.seq)

    @staticmethod
    def __tail_overlap(ol1:str, ol2:str)->str:
        u'''
        returns the end sequence of ol1 matching the start of ol2
        '''
        for i in range(len(ol1)):
            if ol1[i:]==ol2[:len(ol1)-i]:
                return ol1[i:]
        return ""

    def pile_on_sequence(self,seq:str)->str:
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
    batch_id:int=-1
    dist=kwa.get("dist",None)# type: List
    poserr:float=-1.
    pos0:float=-1. # initial (experimental) position in nanometer
    bpos0:float=-1. # initial (experimental) base position
    @initdefaults
    def __init__(self,**kwa):
        super().__init__(**kwa)

class Batch:
    u'''
    Container for Oligo
    '''
    oligos:List[OligoPeak]=[]
    index:int=-1
    @initdefaults
    def __init__(self,**kwa):
        pass

    def fill_with(self,other)->None:
        u'adds oligos from other into self and empties other'
        self.oligos.extend(other.oligos)
        del other.oligos

class BCollection:
    u'''
    Collection of batches
    '''
    oligos:List[OligoPeak] = []
    batches:List[Batch] = []
    @initdefaults
    def __init__(self,**kwa):
        pass

    def from_oligos(self,oligos): # read process (to processor)?
        u''
        grps= {getattr(oli,attr) for oli in oligos}
        batches=[Batch(oligos=[oli for oli in self.oligos if getattr(oli,attr)==grp],index=idx)
                 for idx,grp in enumerate(grps)]
        self.__init__(oligos=oligos,batches=batches)
        

# continue from here
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



# returns number of arrangements to explore, considering only:
#    * arrangements between batches
#    * arrangements between oligos if overlap between oligos is osize-1
# can create a grp object to avoid confusion with regard to the order of the elements in the tuple
def swaps_between_batches(batches, nscale, ooverl): # not great impl # to optimize
    # CAREFUL, misinterpretation of what this function returns.
    # the swap is the new arrangement of peak ids.
    # this returns the indices of the peaks flipped which is in general different from the swap!!
    u'''
    the idea is to reduce the number of arrangements to the minimum.
    2 assumptions :
            * oligos may swap positions if they are within 2 nscale from one another
            * consecutive oligos must have overlap by ooverl bases
    (1) group oligos which may swap due to measurement error
    (2) within each group in (1), cluster oligos if they overlap with osize-1 bases
    (3) compute all combinations of arrangements between batches within each cluster
    (4) to do: not all arrangements between batches should be allowed
               need to discard those which do not have ooverl bases
               -> just use brute force. to discard arrangements
    (5) returns the full list of arrangements to consider
    '''
    oligos = []
    for bat in batches:
        oligos += list(bat.oligos)
    groups = group_overlapping_oligos(oligos,nscale=nscale)

    infogrp=[]
    for grp in groups:
        info=[]
        for val in grp:
            for idx,bat in enumerate(batches):
                if val in bat.oligos:
                    info.append((val,bat.oligos.index(val),idx))
                    break
        infogrp.append(info)

    LOGS.debug("before clustering, %i",len(infogrp))
    finer = []
    for grp in infogrp:
        finer += _cluster_overlapping(ooverl,grp)
    infogrp = list(finer)
    LOGS.debug("after clustering, %i",len(infogrp))
    # generate all arrangements between batches excluding within batch swaps
    swaps = []

    # remove groups if there is not a representative of at least two batches
    infogrp = [grp for grp in infogrp if len(set(val[2] for val in grp))>1]

    for grp in infogrp:
        if len(grp)<2:
            continue
        grpswaps = _groupswaps_between_batches(grp)
        swaps.extend(grpswaps)

    LOGS.debug("len(swaps)=%i", len(swaps))
    return swaps

def _groupswaps_between_batches(grp):
    # can be made more general to include simultaneous
    # merging of more than 2 batches (when necessary)
    # remove swaps which do not satisfy min_overl rule
    # we can define the rules which would allow merging of more than 3-mers
    u'''
    find sequentially the possible arrangements of oligos such that:
        * at least min_overl overlapping bases between consecutive oligos
        * no arrangements between batches
    assumes that oligo indices within the batch are ordered

    # the draft of the more general form
    import queue
    fifos=[]
    for bid in set([i[2] for i in grp]):
        toqueue = sorted([elm for elm in grp if elm[2]==bid],
                         key=lambda x : x[1])
        fifo=queue.PriorityQueue()
        for elm in toqueue:
            fifo.put(elm)
        fifos.append(fifo)


    prange = []
    for idx,fifo in enumerate(fifos):
        prange+=[idx]*fifo.qsize()

    swaps=[]
    # for comb in itertools.permutations(prange):
    # continue from here
    for comb in itertools.combinations(range(len(grp)),len([i for i in grp if i[2]==val])):
        indices = list(range(len(grp)))
        for idx,val in enumerate(subs):
            swap.append()
            # remove indices in swap[-1]
            for i in swap[-1]:
                indices.remove(i)
                swaps.append(swap)
    '''
    bids = list(set(i[2] for i in grp))
    grp1=[i for i in grp if i[2]==bids[0]]
    grp2=[i for i in grp if i[2]==bids[1]]
    combs=[sorted(it) for it in itertools.combinations(range(len(grp)),
                                                       len(grp1))]
    swaps=[]
    for comb in combs:
        swap=list(grp2)
        for index,val in enumerate(comb):
            swap.insert(val,grp1[index])
        swaps.append([i[0] for i in swap])

    return swaps

def _update_seed(ooverl,seed,grp):
    nseed = 0
    while nseed!=len(seed):
        nseed=len(seed)
        for elmt in grp[1:]:
            if elmt[0].seq[:ooverl] in seed:
                seed.update([elmt[0].seq[:ooverl],elmt[0].seq[-ooverl:]])
                continue
            if elmt[0].seq[-ooverl:] in seed:
                seed.update([elmt[0].seq[:ooverl],elmt[0].seq[-ooverl:]])
                continue
    return seed

def _cluster_overlapping(ooverl:int,grp): # to check
    u'''
    a grp is a list of tuples (oligo,oligo index, batch id)
    returns a list of list of (oligo,oligo index, batch id)
    each oligo in a list has ooverl bases with at least another oligo in the same list
    defines rule to swap n-oligos with ooverl overlapping bases
    '''
    # if two oligos are in the same batch they should at least have ooverl overlaps
    # do we put them in the same cluster? yes, we compute arrangements between batches afterwards
    seed = set([grp[0][0].seq[:ooverl],grp[0][0].seq[-ooverl:]])
    seed = _update_seed(ooverl,seed,grp)
    clusters = [[elmt for elmt in grp\
                if elmt[0].seq[:ooverl] in seed or elmt[0].seq[-ooverl:] in seed]]
    allseeds=set(seed)
    while sum(len(i) for i in clusters)!=len(grp):
        # pick a new seed not in seed and restart
        seed = [set([elmt[0].seq[:ooverl],elmt[0].seq[-ooverl:]])\
                for elmt in grp if not elmt[0].seq[:ooverl] in allseeds][0]
        seed = _update_seed(ooverl,seed,grp)
        clusters+=[[elmt for elmt in grp\
                    if elmt[0].seq[:ooverl] in seed or elmt[0].seq[-ooverl:] in seed]]
        allseeds.update(seed)

    return clusters

def can_oligos_overlap(bat1:data.Batch,bat2:data.Batch,min_overl:int=1):
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
