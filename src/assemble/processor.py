#!/usr/bin/env python3
# -*- coding: utf-8 -*-

u'''
regroups functions and classes to complement assembler
'''

import itertools
from typing import List # pylint: disable=unused-import
import numpy
from utils.logconfig import getLogger
from utils import initdefaults

from . import data
from ._types import SciDist

LOGS = getLogger(__name__)

class OptiDistPerm: # pytest
    u'''
    optimize translational cost of permutation
    '''
    perm:Tuple[int] = ()
    dists:List[SciDist] = []
    @initdefaults()
    def __init__(self,**kwa):
        # assert len(perm)==len(dists) # ??
        self._epsi:float = 0.001*min([dists[i].std() for i  in perm])

    def run(self)->numpy.ndarray:
        u'returns the PERMUTATED state which maximise the probability'
        constraints = []
        for idx in range(len(self.perm[:-1])):
            constraints.append({"type":"ineq",
                                "fun":SOMConstraint(idx,self._epsi)})

        xinit = [self.dists[i].mean() for i in self.perm]
        fun = CostPermute(self.dists,self.perm)
        return scipy.optimize.minimize(fun,xinit,constraints=constraints).x

class CostPermute:
    u'returns the "cost" of translations due to permutation of oligo peaks'
    perm:Tuple(int) = ()
    dists:List[SciDist] = []
    @initdefaults
    def __init__(self,**kwa):
        pass
    def __call__(self,xstate):
        return -numpy.product([self.dists[vlp].pdf(xstate[idp])
                               for idp,vlp in enumerate(self.perm)])

class SOMConstraint:
    u'functor for scipy.optimize.minimize constraints'
    index:int = -1
    _epsi:float = -1.0
    @initdefaults
    def __init__(self,**kwa):
        pass
    def __call__(self,xstate):
        return xstate[self.index+1]-xstate[self.index]-self._epsi



class ComputeStates:
    u'Computes possible permutation between'
    # if need to merge 2 by 2 batches, create BCollection of 2 batches?
    collection:BCollection=BCollection()
    nscale:int=1
    ooverl:int=1
    def __init__(self,**kwa):
        pass
    def compute()->numpy.ndarray:
        # cf find_swaps
        # CAREFUL, misinterpretation of what this function returns.
        # the swap is the new arrangement of peak ids.
        # this returns the indices of the peaks flipped which
        # is in general different from the swap!!
        u'''
        returns the new xstates to explore
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
        oligos = self.collection.oligos
        groups = _group_overlapping_oligos(oligos,nscale=self.nscale)

        infogrp=[]
        for grp in groups:
            info=[]
            for val in grp:
                for idx,bat in enumerate(self.batches):
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

        
# continue from here
def _group_overlapping_normdists(dists,nscale=1): # to pytest !! # what if no intersection?
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

def optimal_perm_normdists(perm:List,dists:List)->numpy.ndarray: # pytest
    u'''
    given a permutation perm and the known distributions of each state
    returns the PERMUTATED state which maximise the probability
    '''
    assert len(perm)==len(dists)
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


