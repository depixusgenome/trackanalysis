#!/usr/bin/env python3
# -*- coding: utf-8 -*-

u'''
classes to define Hopping Steps
'''

import sys
from typing import Callable, Iterable # pylint: disable=unused-import
import pickle
import numpy
from utils.logconfig import getLogger
from .oligohit import Batch
from . import _utils as utils

# reconstruction a batch at a time
# if we consider an oligo-batch at a time, then:
#     * permutation can only decrease score
#     * adding a new batch, permutation can only occur between different batches

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
    def __call__(self,*args):
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
        else:
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
        with open("batches.pickle","wb") as testfile:
            pickle.dump(self.batches,testfile)


    def __call__(self,xst):
        u'''
        * requires xstate to add permutations
        * there should be no conflict when adding permutations by construction of the
          optimal_perm_normdists (for 2 by 2 batches merging)
        * what happens when no more permutations are to be explored?
        * needs to return the new position of the oligos
        '''
        LOGS.debug("len(self.batches)="+str(len(self.batches)))
        for perm in find_permutations(self.batches,self.nscale,self.min_overl):
            # from permutations of oligos to permutated positions
            yield perm
        return None


def find_permutations(batches,nscale,min_overl):
    u'''
    for now swap_between_batches allow only merging of 2 batches at a time
    '''
    allperms = []
    while len(batches)>1:
        perms = utils.swap_between_batches([batches[0],batches[1]],nscale,min_overl)
        batches[0].fill_with(batches[1])
        batches.pop(1)
        allperms+=perms
    return allperms

def oli_perm_to_xstate():
    u'''
    translates permutations in oligos to new xstate for basinhopping
    '''
    pass
