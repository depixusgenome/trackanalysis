#!/usr/bin/env python3
# -*- coding: utf-8 -*-


'''
use mcmc to try to converge to a good set of scales
The score is the energy of the spring

new proposal method is to assign inter springs between vertices of different experiments
we can rank the proposals so that they lead to fewer and fewer changes
use iterators

to do:
* still need to apply correction of stre to xeq for different springs
*how to fix the temperature? ...
* consider the best relative of kintra, kinter
* consider Pol's suggestion to put a max penalty score on peaks which do not match any other
* could also set energy of intra springs to zero if the x2-x1-xeq<pos_err
* issue with vertices located at the same position
-> adding LJ potential energy (on top of everything else) is a bit too much for mcmc+L-BFGS-B
-> solution: we know thanks to scl.inter which are the bonded oligos... tree?
-> solution: we could write a optimal solution if we know the springs (we do) to bypass L-BFGS-B

* !! different stretch and bias are considered but no noise on beads (changes of springs)
-> it is probably not useful if kintra is low enough
* !! must include the correct the force of a spring by the stretch applied to it stretch
-> this could easily be tougher than expected
* !! At the moment, the score is based on inter springs which right overlap, but there is some cases
where a vertex is not linked by an intra and is located at the tail of the sequence. This vertex
is unconstrained.
* will be necessary to replace 1.1 (distance between two consecutive oligos) by a named variable



For a spring system
* create inter springs with the constraints that oligos can have
a max of 2 inter springs (left and right)
* calculation of energy would penalize oligos which do not bind on both sides
-> the penalty also applies to first and last oligos so it is just a constant to the energy
* version 1 of used_springs must be improved but is a good basis
* keep  scoring/ minimization "bare"

'''

from typing import List, Dict
import itertools
import scipy.stats
from scipy.optimize import OptimizeResult, basinhopping
from utils.logconfig import getLogger
from assemble.settings import SpringSetting
from assemble.data import Oligo
from spring import Spring
from scores import SpringScore
from stepper import SpringStep
from minimizer import SpringMinimizer

LOGS=getLogger(__name__)

class SpringScaler(SpringSetting): # pylint:disable=too-many-instance-attributes
    '''
    kintra, a tension between oligos in the same peak
    kextra, a directed tension between oligos which may overlap

    kintra allows for gaussian noise around each oligo
    kextra necessary to rescale peaks
    '''

    def __init__(self,**kwa):
        super().__init__(**kwa)
        # scoring and stepper must not be springsettings but inherit springs from scaler
        self.intra:List[Spring]=self.find_intra()
        self.inter:Dict[int,List[Spring]]=self.find_inter()

        self.stepper=SpringStep(intra=self.intra,
                                inter=self.inter,
                                **kwa)
        self.stepper.proposal_call=self.stepper.random_proposal
        self.scoring=SpringScore(intra=self.intra,
                                 inter=self.inter,
                                 **kwa)
        self.minimizer=SpringMinimizer(intra=self.intra,
                                       inter=self.inter,
                                       **kwa)
        self.res:List[OptimizeResult]=[]
        self.peakid:int=kwa.get("peakid",0) # id of peak to update
        self.basinkwa={"func":self.scoring,
                       "niter":100,
                       "minimizer_kwargs":dict(method=self.minimizer),
                       "take_step":self.stepper,
                       "T":1}

    def find_intra(self)->List[Spring]:
        'add springs within an experiment'
        intra:List[Spring]=[]
        for pkids in self.peakids:
            intra.extend([Spring(type="intra",
                                 force=self.kintra,
                                 xeq=abs(self._fpos[id1]-self._fpos[id2]),
                                 id1=id1,id2=id2)
                          for id1,id2 in zip(pkids[:-1],pkids[1:])])
        return intra

    def find_inter(self)->Dict[int,List[Spring]]:
        '''
        add springs between experiments
        also includes springs with force 0 to account for
        oligos within experiment which are supposed to overlap
        '''
        signs=(0,0) if self.unsigned else (1,1)
        inter:Dict[int,List[Spring]]={idx:[] for idx in range(len(self._olis))}
        overlap=lambda x,y:Oligo.overlap(x,y,
                                         min_overl=self.min_overl,
                                         signs=signs,
                                         shift=1)

        # between experiments
        for exp1,exp2 in itertools.permutations(self.peakids,2):
            for id1,id2 in itertools.product(exp1,exp2):
                if overlap(self._olis[id1],self._olis[id2]):
                    inter[id1].append(Spring(type="inter",
                                             force=self.kinter,
                                             xeq=1.1,
                                             id1=id1,
                                             id2=id2))

        # within experiments
        # applying force 0 to not interfere with intra
        # whilst allowing to consider the fact that the 2 are supposed to overlap
        for pkid in self.peakids:
            for id1,id2 in zip(pkid[:-1],pkid[1:]):
                if overlap(self._olis[id1],self._olis[id2]):
                    inter[id1].append(Spring(type="inter",
                                             force=0,
                                             xeq=abs(self._fpos[id1]-self._fpos[id2]),
                                             id1=id1,
                                             id2=id2))

        return inter

    def run(self,repeats:int=1):
        '''
        runs mcmc steps on a single peak at a time
        '''
        state=self._fpos
        chains=itertools.chain.from_iterable(itertools.repeat(range(len(self.peaks)),repeats))
        for peakid in chains:
            self.stepper.peakid=peakid
            curr_res=basinhopping(x0=state,**self.basinkwa)
            LOGS.debug(f"fun={curr_res.fun}")
            self.res.append(curr_res)
            state=curr_res.x

        return state

    def ordered_oligos(self,state)->List[Oligo]:
        'returns the ordered list of oligos according to state'
        # order=sorted([(state[idx],self._olis[idx]) for idx in range(len(self._olis))],
        #              key=lambda x:x[0])
        # return [oli[1] for oli in order]
        oligos=[self._olis[idx].copy(pos=state[idx],
                                     dist=scipy.stats.norm(loc=state[idx],
                                                           scale=self._olis[idx].poserr))
                for idx in range(len(self._olis))]
        return sorted(oligos,key=lambda x:x.pos)
