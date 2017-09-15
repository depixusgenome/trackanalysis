#!/usr/bin/env python3
# -*- coding: utf-8 -*-


'''
need to find a good way to explore the sensibly the different possible combinations
'''

from typing import List, Dict, Tuple
import itertools
import random
import numpy as np
import scipy.stats
from utils.logconfig import getLogger
from settings import SpringSetting
from assemble.data import Oligo
from assemble.scaler import match_peaks
from spring import Spring

LOGS=getLogger(__name__)

class SpringStepExhaust(SpringSetting):
    '''
    Is there a way to generate all possible spring system?
    Can we order them ?
    '''
    pass

class SpringStep(SpringSetting): # pylint: disable=too-many-instance-attributes
    '''
    each moves consists of two steps for each experiment
    a move of all oligos within a peak
    a move for each oligos
    '''
    def __init__(self,**kwa):
        super().__init__(**kwa)
        scale=0.5 # large scale for stretch
        loc=1.0
        stre=(self.bstretch.lower,self.bstretch.upper)
        self.stredist=scipy.stats.truncnorm(a=(stre[0]-loc)/scale,
                                            b=(stre[1]-loc)/scale,
                                            loc=loc,scale=scale).rvs
        self.biasdist=scipy.stats.uniform(loc=self.bbias.lower,
                                          scale=self.bbias.upper-self.bbias.lower).rvs
        self.intra:List[Spring]=kwa.get("intra",[])
        self.inter:Dict[int,List[Spring]]=kwa.get("inter",{})
        self.peakid:int=kwa.get("peakid",0) # index of peakid to update
        self.rneighs:Dict[int,Tuple[int]]=self.find_neighbors(side="right")
        self.lneighs:Dict[int,Tuple[int]]=self.find_neighbors(side="left")
        self.proposal_call=self.random_proposal #self.proposal

    def find_neighbors(self,side)->Dict[int,Tuple[int, ...]]:
        '''
        returns the indices of self._olis which overlap on the right of given key
        '''
        overlap=Oligo.overlap
        signs=(0,0) if self.unsigned else (1,1)
        neighs={}
        if side=="right":
            for idx, oli in enumerate(self._olis):
                neighs[idx]=tuple(frozenset([idy
                                             for idy in range(len(self._olis))
                                             if overlap(oli.seq,
                                                        self._olis[idy].seq,
                                                        signs=signs,
                                                        min_overl=self.min_overl,
                                                        shift=1)]))
        else:
            for idx, oli in enumerate(self._olis):
                neighs[idx]=tuple(frozenset([idy
                                             for idy in range(len(self._olis))
                                             if overlap(self._olis[idy].seq,
                                                        oli.seq,
                                                        signs=signs,
                                                        min_overl=self.min_overl,
                                                        shift=1)]))
        return neighs

    def __call__(self,*args):
        '''
        updates a single peak and returns the position which minimizes the energy due to that peak
        '''
        state=args[0]
        prop=self.proposal_call(state)

        if prop is None:
            return state

        # apply stretch, bias and noise to peakid
        stre,bias=prop
        nstate=state.copy()
        nstate[self.peakids[self.peakid]]=stre*self._pos[self.peakid]+bias
        return nstate


    def random_proposal(self,state:np.array):
        '''
        More flexible proposal.
        Does not check matching of new proposal.
        Allows wider rearrangement of peaks
        To use with SpringScaler, NOT with SpringCluster
        '''
        tomatch=np.sort(np.hstack([state[pkid]
                                   for pkid in range(len(self.peakids))
                                   if pkid!=self.peakid]))
        matches=match_peaks(tomatch,
                            self._pos[self.peakid],
                            self.bstretch,
                            self.bbias)
        if not matches:
            LOGS.debug(f"no proposal for peak id {self.peakid}")

        if matches:
            return random.choice(matches) # type: ignore
        return None

    # TO FIX: assumes that rneighs and lneighs belong to different peaks
    # -> this overestimate the number of possible scales (not necessarily a huge deal)
    # Does not allow enough flexibility
    # to apply a random arrangement
    def proposal(self,state:np.array):
        '''
        testing,
        a scale is not proposed if the matched vertex is already overlapping
        with another
        '''
        all_left=frozenset([idx for pkid in self.peakids[self.peakid]
                            for idx in self.lneighs[pkid]])
        # removing indices of left if they overlap on their right
        rmleft=frozenset([idx for idx in all_left
                          if any([abs(state[idx]-state[idy])<1.5
                                  for idy in self.rneighs[idx]])])
        # if rmleft:
        #     for idx in all_left:
        #         print(f"idx={idx}")
        #         print(f"state={state}")
        #         print([abs(state[idx]-state[idy])<1.5
        #                for idy in self.rneighs[idx]])
        all_right=frozenset([idx for pkid in self.peakids[self.peakid]
                             for idx in self.rneighs[pkid]])
        rmright=frozenset([idx for idx in all_right
                           if any([abs(state[idx]-state[idy])<1.5
                                   for idy in self.lneighs[idx]])])
        left=list(all_left-rmleft)
        right=list(all_right-rmright)
        tomatch=np.sort(np.hstack([np.array(state[left])-1.1,np.array(state[right])+1.1]))
        matches=match_peaks(tomatch,
                            self._pos[self.peakid],
                            self.bstretch,
                            self.bbias)
        if not matches:
            LOGS.debug(f"no proposal for peak id {self.peakid}")

        if matches:
            # print(f"len(matches)={len(matches)}")
            return random.choice(matches) # type: ignore
        return None

    # TO FIX
    def find_crystal(self,state:np.array)->List[Tuple[int, ...]]:
        '''
        there is crystallisation of two or more experiments if
        their oligos overlap and that 2 oligos from different peaks
        are located at 1.1 from one another
        needs more complexity eg:
        if (tgt) and (gtg,gtg) when (gtg,tgt,gtg) is the correct solution
        '''
        esp=0.25
        signs=(0,0) if self.unsigned else (1,1)
        overlap=lambda seq1,seq2:Oligo.overlap(seq1,
                                               seq2,
                                               signs=signs,
                                               min_overl=self.min_overl,
                                               shift=1)
        oneway=lambda seq1,seq2:overlap(seq1,seq2) and not overlap(seq2,seq1)
        groups:List[Tuple[int, ...]]=[]
        for idx1,idx2 in itertools.permutations(range(len(state)),2):
            if (state[idx2]-state[idx1]-1.1)**2<esp:
                if oneway(self._olis[idx2].seq,self._olis[idx1].seq):
                    groups.append((idx1,idx2))

        return groups

    def new_proposal(self,state:np.array):
        '''
        given the current position of oligos,
        try to propose a new position for oligos in self.peakid
        where 2 vertices do not occuppy the same sphere
        '''
        pass
