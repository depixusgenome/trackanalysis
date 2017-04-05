#!/usr/bin/env python3
# -*- coding: utf-8 -*-

u'''
classes to define Hopping Steps
'''

import sys
from typing import Callable, Iterable # pylint: disable=unused-import
import itertools
import numpy
from . import _utils as utils
from oligohit import Batch

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

    # segregate per batch permutation beteen oligos with same batch_id is forbidden
    # -> better for recursive, scaffolding
    # segregate per batch permutation beteen oligos with same sequence is forbidden

    '''
    def __init__(self,**kwargs):
        super().__init__(**kwargs)
        self.oligos = kwargs.get("oligos",tuple())
        self.nscale = kwargs.get("nscale",1)
        self.seg = kwargs.get("seg","batch_id") # "batch", "sequence"
        self.swaps = []

        # create Batches from each batch_ids move from one Batch to another
        batchids = list(set(i.batch_id for i in self.oligos))
        self.batches = [Batch(oligos=[i for i in self.oligos if i.batch_id==index],
                              index=index)
                        for index in batchids]

        # batches from groups( = utils.group_oligos(self.oligos, by=self.seg))?? 

        self.swaps_from_batches()
                    
    def __call__(self,xst):
        u'''
        should be something like
        '''
        swaps = self.swaps_from_batches()
        while swaps:
            for swp in swaps:
                yield swp
            swaps=self.swaps_from_batches()

    def swaps_from_batches(self):
        u'returns swaps between the first two batches then merges them'
        if len(self.batches)<2:
            return None

        grp_ovl=utils.group_overlapping_oligos
        swaps = [it for it in itertools.product(self.batches[0], self.batches[1])
                 if len(grp_ovl(it))==1]
        self.batches[0].fill_with(self.batches[1])
        self.batches.pop(1)
        return swaps
        
