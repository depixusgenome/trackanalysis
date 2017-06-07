#!/usr/bin/env python3
# -*- coding: utf-8 -*-

u'''
classes to define Hopping Steps
In the case of OptimOligoSwap, we can run :
    * the merging of batches 2 by 2 then look at regions where better solutions can be found
      by merging simultanesouly more batches
    * or run the full set of possibilities
          -> pb: requires about 16 minutes to run at current precision
          -> solution has already been partially implemented in _perms_in_groups_between_batches

'''


import sys
from typing import Callable, Iterable, List, Tuple # pylint: disable=unused-import
import pickle
import numpy
from utils.logconfig import getLogger
from .oligohit import Batch
from .data import KPerm
#from . import _utils as utils

# to add variability in (stretching,bias) for each batch (to estimate from hybridstat analyses)

LOGS = getLogger(__name__)

class HoppingSteps:
    u'''
    defines boundaries, steps for basinhopping
    Can forbid flipping of peaks within the same batch
    '''
    def __init__(self,**kwargs):
        self.min_x = kwargs.get("min_x",0)
        self.max_x = kwargs.get("max_x",sys.maxsize)
        self.scale = kwargs.get("scale",1)
        self.dists = kwargs.get("dists",[]) # list of distributions
        self.random_state = kwargs.get("random_state",None)
    def __call__(self,xstate): # should be overriden
        pass

class PreFixedSteps(HoppingSteps):
    u'''
    calls predefined fixed distributions
    '''
    def __call__(self,*args): # pylint: disable=arguments-differ
        return numpy.array([i.rvs(random_state=self.random_state) for i in self.dists])


class GaussAndFlip(HoppingSteps):
    u'''for two calls, one uses defined dists
    the other randomly flips 2 consecutive xstates
    '''
    def __init__(self,**kwargs):
        super().__init__(**kwargs)
        self.count = 0
    def __call__(self,xst):
        if self.count==0:
            self.count=1
            return numpy.array([i.rvs(random_state=self.random_state) for i in self.dists])

        self.count=0
        flip = numpy.random.randint(len(xst)-1)
        xst[flip], xst[flip+1] = xst[flip+1],xst[flip]
        return xst

class OptimOligoSwap(HoppingSteps): # not yet usable
    u'''
    trying to optimize the exploration of param space given hypotheses:
    symetric distribution of z around z0 (gaussian at the moment)
    find the distribution which overlap (and allow permutation of oligos)

    batches need to be merged such that the previous merge are more contrainted than the laters
    '''
    def __init__(self,**kwargs):
        super().__init__(**kwargs)
        self.oligos = kwargs.get("oligos",tuple())
        self.nscale = kwargs.get("nscale",1)
        self.seg = kwargs.get("seg","batch_id") # "batch", "sequence"
        self.min_overl = kwargs.get("min_overl",1)
        self.swaps = []

        # create Batches from each batch_ids move from one Batch to another
        batchids = list(set(i.batch_id for i in self.oligos))
        # need to order batch : by decreasing number of peaks
        # batch needs to be merged in a given order to maximize constraints
        # can only merge batches if oligos overlap by n-1
        self.batches = [Batch(oligos=[i for i in self.oligos if i.batch_id==index],
                              index=index) for index in batchids]
        # batches from groups( = utils.group_oligos(self.oligos, by=self.seg))??
        swaps = [KPerm(i) for i in find_swaps(self.batches,self.nscale,self.min_overl)]
        print("len(swaps)=",len(swaps))
        with open("swaps.pickle","wb") as testfile:
            pickle.dump(swaps,testfile)
        self.perms = [] #from_swaps2perms(swaps)

    def __call__(self,xst):
        u'''
        * problem when adding permutations:
             -> if it overlaps with any other permutations
                (a new permutation to test includes an oligo already permuted)
             -> if the 2 permutations are independent (do not involve the same oligos)
        * requires xstate to add permutations
        * there should be no conflict when adding permutations by construction of the
          optimal_perm_normdists (for 2 by 2 batches merging)

        return the new position of the oligos
        '''
        LOGS.debug("len(self.batches)="+str(len(self.batches)))
        for perm in self.perms:
            # from permutations of oligos to permutated positions
            yield oli_perm_to_xstate(self.oligos,perm)
        return None


def find_swaps(batches,nscale,min_overl):
    u'''
    for now swap_between_batches allow only merging of 2 batches at a time
    '''
    allswaps = []
    while len(batches)>1:
        print(nscale,min_overl)
        swaps = [] # utils.swaps_between_batches([batches[0],batches[1]],nscale,min_overl)
        if any(numpy.array([len(i) for i in swaps])<2):
            LOGS.warning("problem with swap size")
        batches[0].fill_with(batches[1])
        batches.pop(1)
        allswaps+=swaps
    return allswaps

def oli_perm_to_xstate(oligos,argntsid)->numpy.ndarray:
    u'''
    operm is the oligos permuting (in that order)
    perm (1,2) is neutral with regard to permutation
    (2,1) is not
    perm (i,j,k,l,m) i,j,k,l,m are the oligos whose order has changed
    eg (4512) 4 is now in position of 1, 5 of 2 etc...
    '''
    #needs to be generic :
    #    * if 2 oligos are permuted, need to consider all oligos between these 2 oligos
    #    * what if a permutation already occured

    # find indices of permuted oligos in oligos
    #opermid = [oligos.index(oli) for oli in operm]

    ids2perm = {sorted(argntsid)[idx]:val for idx,val in enumerate(argntsid)}
    permids = list(range(len(oligos)))
    for key,value in ids2perm.items():
        permids[key]=value

    return numpy.empty(shape=(1,))
    #return utils.optimal_perm_normdists(permids,[oli.dist for oli in oligos])[permids]
