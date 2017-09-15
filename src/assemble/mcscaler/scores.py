#!/usr/bin/env python3
# -*- coding: utf-8 -*-


'''
scoring a system of springs for scaling
'''

from typing import List, Dict, FrozenSet
import numpy as np
from utils.logconfig import getLogger
from assemble.settings import SpringSetting
import assemble.data as data
from spring import Spring

LOGS=getLogger(__name__)

class SpringScore(SpringSetting):
    '''
    uses springs to scale experiments
    for inter springs take the minimal spring
    For inter spring we look at those corresponding to right overlaps
    the id with minimal pos has an energy of 0
    need to add condition that 2 oligos cannot right overlap with the same oligo
    '''
    def __init__(self,**kwa):
        super().__init__(**kwa)
        self.poserr=kwa.get("poserr",5)
        self.intra:List[Spring]=kwa.get("intra",[])
        self.inter:Dict[int,List[Spring]]=kwa.get("inter",{})

    def __call__(self,*args,**kwa):
        'testing a cleaner __call__'
        state=args[0]
        springs=list(self.intra)+self.used_springs(self.inter,state)
        return self.energy_system(springs,state)

    @staticmethod
    def noverlaps(oligos,state,unsigned=True,min_overl=0)->int:
        '''
        returns the number of overlaps between consecutive oligos
        advantage of this is the robustness with regard to missing peaks
        state should be minimized such that inter springs connect neighbours oligos
        '''

        sorted_olis=sorted([(pos,oligos[idx])
                            for idx,pos in enumerate(state)],
                           key=lambda x:x[0])
        seqs=[oli[1].seq for oli in sorted_olis]
        # should/will count the number of overlaps of k-1, k-2 etc...

        signs=(0,0) if unsigned else (1,1)
        overlap=lambda x,y,z:data.Oligo.overlap(x,
                                                y,
                                                shift=1,
                                                min_overl=z,
                                                signs=signs)
        return sum([min_overl for seq1,seq2 in zip(seqs[:-1],seqs[1:])
                    if overlap(seq1,seq2,min_overl)])

    @staticmethod
    def energy_system(springs,state):
        'returns the total energy of the system of spring'
        scores=[spr.energy(state[spr.id1],state[spr.id2]) for spr in springs]
        #penalty=np.sum((np.sort(state)[1:]-np.sort(state)[:-1])<1.1)
        return sum(scores)#+100*penalty

    @staticmethod
    def penalised_energy(springs,state,poserr):
        '''
        total energy of the system of spring
        plus a penalty (based on poserr)
        applied to each oligos which do not have inter spring
        on either side
        '''
        scores=[spr.energy(state[spr.id1],state[spr.id2]) for spr in springs]
        left=frozenset([spr.id1 for spr in springs if spr.type=='inter'])
        right=frozenset([spr.id2 for spr in springs if spr.type=='inter'])
        unmatched=len([idx for idx in range(len(state)) if not idx in left])
        unmatched+=len([idx for idx in range(len(state)) if not idx in right])
        return sum(scores)+unmatched*(2*poserr)**2

    # version 2, seems to behave correctly.
    # the issue is now to find a way such that all scales are eventually explored
    @staticmethod
    def used_springs(inter,state:np.array)->List[Spring]:
        '''
        newer implementation of used_springs
        1 oligo can only bind once on 1 side
        drawbacks:
        * need to add inter springs (to represent overlapping between consecutive oligos)
        iff the distance is below a given threshold (depending on poserr. 2*poserr?)
        penalised_energy will catch non-matched oligos
        '''
        energies=sorted([(spr.energy(state[spr.id1],state[spr.id2]),spr.id1,spr.id2,spr)
                         for key,springs in inter.items()
                         for spr in springs],key=lambda x:x[0])
        left:FrozenSet[int]=frozenset([])
        right:FrozenSet[int]=frozenset([])
        inters:List[Spring]=[]
        for spr in energies:
            if spr[1] in left or spr[2] in right:
                continue
            inters.append(spr[3])
            left=left.union(frozenset([spr[1]]))
            right=right.union(frozenset([spr[2]]))
        return inters
