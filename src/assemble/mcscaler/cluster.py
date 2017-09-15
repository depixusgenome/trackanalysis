#!/usr/bin/env python3
# -*- coding: utf-8 -*-


'''
Not fully implemented yet
provides an alternative way to explore possible combination of oligo experiments
'''

from typing import NamedTuple
import numpy as np
from utils.logconfig import getLogger
from assemble.scaler import OPeakArray
from scores import SpringScore
from scaler import SpringScaler


LOGS=getLogger(__name__)

Match2Peaks=NamedTuple("Match2Peaks",[("score",float),("nmatches",int),("peak",OPeakArray)])


# bugged in the position of the oligos after cluster.
# stretch, bias boundaries are not respected!
# must conserve the inter springs used to prefer one cluster over another
# the old inter+intra springs become the new intra springs.
# preserves coehrency of the cluster
class SpringCluster(SpringScaler):
    '''
    The idea is to focus on a very small subset (2, max 3) set of peaks
    and call SpringScaler on them to find the best match..
    rinse and repeat
    '''

    def __init__(self,**kwa):
        super().__init__(**kwa)
        self.kwargs=kwa
        self.scaler:SpringScaler

    # needs improvements
    # to fix: clustered peaks must conserve inter springs
    # otherwise the find_equilibirum will tear the clustered springs apart
    def cluster2peaks(self,
                      exp1:OPeakArray,
                      exp2:OPeakArray)->Match2Peaks:
        '''
        find the best way to stack to peaks together
        exp1 is considered fixed
        one stretches and gets biased for the 2
        could use:
                      stretches:Tuple[Bounds,...],
                      biases:Tuple[Bounds,...])->OPeakArray:
        '''
        # faster implementation and testing
        # the mcmc scoring defines which is best in terms of k1, k2
        self.scaler=SpringScaler(**dict(list(self.kwargs.items())+[("peaks",[exp1,exp2])]))
        self.scaler.basinkwa["niter"]=500
        self.scaler.stepper.proposal_call=self.scaler.stepper.random_proposal
        state=self.scaler.run(repeats=1)
        # can rescale state such that one point is fixed (conserves stretch and bias boundaries)
        # can compute the number of springs involved for normalisation
        nmatches=len(SpringScore.used_springs(self.scaler.inter,state))
        score=self.scaler.res[-1].fun

        # testing meanshift
        meanshift=np.mean(np.hstack([exp1.posarr,exp2.posarr]))-np.mean(state)
        peak=OPeakArray(arr=self.scaler.ordered_oligos(state),
                        min_overl=self.min_overl)+meanshift
        # returns the best result
        return Match2Peaks(score=score,
                           nmatches=nmatches,
                           peak=peak)

    # should consider only those who have more than 1 event
    def cluster(self):
        '''
        main clustering process which tries to add to peaks[0]
        a peak at a time
        probably better to leave off clustering of peaks with single event
        '''
        signs=(0,0) if self.unsigned else (1,1)
        overlap=lambda peak1,peak2: peak1.overlap_with(peak2,
                                                       min_overl=self.min_overl,
                                                       signs=signs,
                                                       shift=1)

        assigned=[False]*len(self.peakids)
        assigned[0]=True
        cluster=self.peaks[0].copy()
        # all_matches:List[Match2Peaks]=[]
        while not all(assigned):
            print(f"unassigned={assigned.count(False)}")
            # assign=assigned.index(False)
            # matches:List[Match2Peaks]=[] # scores and clusters
            neighs=[pkid for pkid,peak in enumerate(self.peaks)
                    if not assigned[pkid] and overlap(cluster,peak)]
            neighs+=[pkid for pkid,peak in enumerate(self.peaks)
                     if not assigned[pkid] and overlap(peak,cluster)]
            neighs=list(frozenset(neighs))
            print(f'len(neighs)={len(neighs)}')
            print(f'neighs={neighs}')
            # scores and clusters
            matches=[(self.cluster2peaks(cluster,self.peaks[neigh]),neigh) for neigh in neighs]
            matches=sorted(matches,key=lambda x:x[0].score/x[0].nmatches)
            cluster=matches[0][0].peak
            assigned[matches[0][1]]=True
        return cluster

# Notes :
# (1) when computing the equilibrium of the spring system,
# we do not take into account the stretch and bias
# (2) CLUSTERING: non-paired vertices are penalising clustering
# score (must include a threshold poserr)
# (3) CLUSTERING: there is not penalty score for vertices occupying the same space
