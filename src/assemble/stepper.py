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

    # strategies:
    # find each groups of oligos, take itertools.product(groups) find overlaps is too long!
    # find overlapping oligos, find different groups for each overlapping set
    '''
    def __init__(self,**kwargs):
        super().__init__(**kwargs)
        self.oligos = kwargs.get("oligos",[])
        self.nscale = kwargs.get("nscale",1)
        self.seg = kwargs.get("seg","batch_id") # "batch", "sequence"
        # find overlapping oligos
        # for each overlapping group, find the different groups, within overlapping oligos
        #overoli = utils.find_overlapping_oligos(self.oligos,nscale=nscale)
        #self.perms = []
        #for overgrp in overoli:
        #    groups = utils.group_oligos(overgrp,by=self.seg)
        #    print("len(groups)=",len(groups))
        #    for pro in itertools.product(*groups):
        #        self.perms.append(pro) # perms contains duplicate permutations

        # set the calls such that __call__ tends to merge batches together
        #batches = set(i.batch_id for i in self.oligos)
        groups = utils.group_oligos(self.oligos, by=self.seg)
        import pickle
        pickle.dump(groups,open("groups.pickle","wb"))
        self.swaps = []
        # define generators of generators?
        # group i and i+1

        # can't do overoli first because find_overlapping_oligos does not return a partition
        grp_ovl=utils.group_overlapping_oligos
        for idg,grp in enumerate(groups[1:]):
            # find overlapping oligos
            # if they belong to 2 groups add a swap
            self.swaps.extend([it for it in itertools.product(grp,groups[idg])
                               if len(grp_ovl(*it))==1])


    def __call__(self,xst):
        u'''
        should be something like
        '''
        for swp in self.swaps:
            yield swp
