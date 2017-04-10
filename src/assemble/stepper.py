#!/usr/bin/env python3
# -*- coding: utf-8 -*-

u'''
classes to define Hopping Steps
'''

import sys
from typing import Callable, Iterable # pylint: disable=unused-import
import itertools
import numpy
from .oligohit import Batch
from . import _utils as utils

# reconstruction a batch at a time
# if we consider an oligo-batch at a time, then:
#     * permutation can only decrease score
#     * adding a new batch, permutation can only occur between different batches

# to add variability in (stretching,bias) for each batch (to estimate from hybridstat analyses)

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
        self.swaps = []

        # create Batches from each batch_ids move from one Batch to another
        batchids = list(set(i.batch_id for i in self.oligos))
        # need to order batch : by decreasing number of peaks
        # batch needs to be merged in a given order to maximize constraints
        # can only merge batches if oligos overlap by n-1
        self.batches = [Batch(oligos=[i for i in self.oligos if i.batch_id==index],
                              index=index)
                        for index in batchids]
        # batches from groups( = utils.group_oligos(self.oligos, by=self.seg))??

        self.swap_batches()

    def __call__(self,xst):
        u'''
        * should be something like (see impl)
        * requires xstate to add permutations
        * there should be no conflict when adding permutations by construction of the
          optimal_perm_normdists
        * what happens when no more permutations are to be explored?

        to fix:
        while swaps:
            for swp in swaps:
                yield swp
            swaps = self.swap_batches()
        return None
        '''
        print("len(self.batches)=",len(self.batches))
        return self.swap_batches()

    def swap_batches(self):
        u'''
        takes two batches, if there can be an overlap between oligos in the two batches,
        compute swaps
        returns swaps between two batches.
        These batches are then merged
        '''
        if len(self.batches)==1:
            return None

        # what if no batches can overlap?
        # corresponds to primed batches does for which we have no info
        swaps = None
        for merges in itertools.combinations(range(len(self.batches)),2):
            if utils.can_oligos_overlap(self.batches[merges[0]],
                                        self.batches[merges[1]],
                                        min_overl=3):
                swaps = utils.swap_between_batches(self.batches[merges[0]],
                                                   self.batches[merges[1]],
                                                   nscale = self.nscale)
                self.batches[merges[0]].fill_with(self.batches[merges[1]])
                self.batches.pop(merges[1])
                break
        # remove swaps if oligos are note permuted??
        return swaps
