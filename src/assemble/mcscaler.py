#!/usr/bin/env python3
# -*- coding: utf-8 -*-


'''
use mcmc to try to converge to a good set of scales
The score is the energy of the spring

to do:
optimal position -> L-BFGS-B
also forbid the the overlap of 2 or more peak
 -> L-BFGS-B
* still need to apply correction of stre to xeq for different springs
*how to fix the temperature? ...
* consider the best relative of kintra, kinter
* consider Pol's suggestion to put a max penalty score on peaks which do not match any other
* could also set energy of intra springs to zero if the x2-x1-xeq<pos_err
* issue with vertices located at the same position
-> adding LJ potential energy (on top of everything else) is a bit too much for mcmc+L-BFGS-B
-> solution: we know thanks to scl.inter which are the bonded oligos... tree?
-> solution: we could write a optimal solution if we know the springs (we do) to bypass L-BFGS-B

* !! different stretch and bias are considered but
  we also need different noise on beads (changes of springs)
* !! must include the correct the force of a spring by the stretch applied to it stretch
-> this could easily be tougher than expected
'''

from typing import List, Dict, Tuple, Callable, Iterable, NamedTuple, FrozenSet # pylint: disable=unused-import
import itertools
import random
import networkx
import numpy as np
import scipy.stats
from scipy.optimize import OptimizeResult, basinhopping
from utils.logconfig import getLogger
from assemble.settings import SpringSetting
import assemble.data as data
import assemble.scaler as scaler

LOGS=getLogger(__name__)

def make_graph(peaks,bstretch,bbias,min_overl=2,unsigned=True):
    '''
    creates a graph where each oligo expirement is a node
    '''
    # the first (larger) tree (DiGraph) checks if there is overlapping (unsigned==True)
    # between peaks seqs
    edges1=[(p1,p2)
            for p1,p2 in itertools.permutations(peaks,2)
            if scaler.OPeakArray.may_overlap(p1,[p2],min_overl=min_overl,unsigned=unsigned)]

    # the second (sub-tree) contains only edges between peaks which can be matched by stretch,bias
    edges2=[edge for edge in edges1 if scaler.match_peaks(edge[0].posarr,
                                                          edge[1].posarr,
                                                          bstretch,
                                                          bbias)]

    # find all paths starting with a given peakid
    graph=networkx.DiGraph()
    graph.add_edges_from(edges2)
    return graph


class Spring:
    'models a spring'
    def __init__(self,**kwa):
        self.type:str=kwa.get("type","")
        self.force:float=kwa.get("force",0)
        self.xeq:float=kwa.get("xeq",0)
        self.id1:int=kwa.get("id1",0)
        self.id2:int=kwa.get("id2",0)

    def energy(self,xpos1,xpos2):
        'returns energy on the spring'
        return self.force*(xpos2-xpos1-self.xeq)**2

    def tension(self,xpos1,xpos2):
        'returns the tension applied on the spring'
        return 2*self.force*(xpos2-xpos1-self.xeq)

    @property
    def ids(self)->Tuple[int, ...]:
        "ids"
        return tuple([self.id1,self.id2])

# # probably no longer useful
# def get_Jacobian(intra,inter,state):
#     'returns Jacobian'
#     springs=list(intra)+SpringScore.used_springs(inter,state)
#     jac=np.array([0]*len(state))
#     for idx,_ in enumerate(jac):
#         force=sum([spr.tension(state[spr.id1],state[spr.id2]) for spr in springs if idx==spr.id1])
#         force+=sum([-spr.tension(state[spr.id1],state[spr.id2])
#                     for spr in springs if idx==spr.id2])
#         jac[idx]=force
#     return jac

class SpringStep(SpringSetting): # pylint: disable=too-many-instance-attributes
    '''
    each moves consists of two steps for each experiment
    a move of all oligos within a peak
    a move for each oligos
    '''
    def __init__(self,**kwa):
        super().__init__(**kwa)
        self.poserr:float=kwa.get("poserr",1.0)
        scale=0.5 # large scale for stretch
        loc=1.0
        stre=(self.bstretch.lower,self.bstretch.upper)
        self.stredist=scipy.stats.truncnorm(a=(stre[0]-loc)/scale,
                                            b=(stre[1]-loc)/scale,
                                            loc=loc,scale=scale).rvs
        self.biasdist=scipy.stats.uniform(loc=self.bbias.lower,
                                          scale=self.bbias.upper-self.bbias.lower).rvs
        # self.noise=scipy.stats.norm(loc=0.,
        #                             scale=self.poserr).rvs
        self.intra:List[Spring]=kwa.get("intra",[])
        self.inter:Dict[int,List[Spring]]=kwa.get("inter",{})
        self.peakid:int=kwa.get("peakid",0) # index of peakid to update
        self.rneighs:Dict[int,Tuple[int]]=self.find_neighbors(side="right")
        self.lneighs:Dict[int,Tuple[int]]=self.find_neighbors(side="left")

    # must not include bstretch, bbias to limit calculations
    def find_neighbors(self,side)->Dict[int,Tuple[int, ...]]:
        '''
        returns the indices of self._olis which overlap on the right of given key
        '''
        overlap=data.Oligo.overlap
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
        prop=self.proposal(state)

        if prop is None:
            return state

        # apply stretch, bias and noise to peakid
        stre,bias=prop
        nstate=state.copy()
        nstate[self.peakids[self.peakid]]=stre*self._pos[self.peakid]+bias #+noise
        return nstate

    def proposal(self,state:np.array):
        '''
        given the current position of oligos,
        try to propose a new position for oligos in self.peakid
        '''
        left=list(frozenset([idx for pkid in self.peakids[self.peakid]
                             for idx in self.lneighs[pkid]]))
        right=list(frozenset([idx for pkid in self.peakids[self.peakid]
                              for idx in self.rneighs[pkid]]))

        tomatch=np.sort(np.hstack([np.array(state[left])-1.1,np.array(state[right])+1.1]))
        matches=scaler.match_peaks(tomatch,
                                   self._pos[self.peakid],
                                   self.bstretch,
                                   self.bbias)
        if not matches:
            LOGS.debug(f"no proposal for peak id {self.peakid}")

        if matches:
            return random.choice(matches) # type: ignore
        return None

class SpringMinimizer:
    'regroups the different ways to minimize the spring network'
    def __init__(self,**kwa):
        self.intra:List[Spring]=kwa.get("intra",[])
        self.inter:Dict[int,List[Spring]]=kwa.get("inter",dict())
        self.call:Callable=kwa.get("method",self.no_noise)

    def __call__(self,*args,**kwa):
        return self.call(self,*args,**kwa)

    def no_noise(self,_,_2,*args, **kwa): # pylint: disable=unused-argument
        'finds equilibrium of a system of springs'
        xinit=args[0]
        springs=list(self.intra)+SpringScore.used_springs(self.inter,xinit)
        equil=self.find_equilibrium(springs)

        if equil is None:
            return OptimizeResult(x=xinit,
                                  fun=SpringScore.score_springs(springs,xinit),
                                  success=True,
                                  nfev=1)
        equil=xinit[0]+np.array([0.0]+equil)
        return OptimizeResult(x=equil,
                              fun=SpringScore.score_springs(springs,equil),
                              success=True,
                              nfev=1)

    def with_noise(self,fun, xinit, *args, **kwa): # pylint: disable=unused-argument
        '''
        allows vertices to be moved up to a given value
        which will result in different spring networks
        returns the one with minimal energy
        '''
        # compute the set of springs for each possible moved vertex
        # does not necessarily require __hash__ and __eq__ of Spring
        # for each springs compute the equilibrium
        # energy(*(springs,equil)) for (springs,equil) in sprequilibria
        pass

    @staticmethod
    def no_minimizer(fun, xinit, *args, **options): # pylint: disable=unused-argument
        '''
        use this minimizer to avoid minimization step in basinhopping
        '''
        return OptimizeResult(x=xinit, fun=fun(xinit), success=True, nfev=1)

    @staticmethod
    def find_equilibrium(springs:List[Spring]):
        '''
        solves the SpringSystem
        this function computes the equilibrium, not the minimisation of energy
        '''
        # build the connectivity matrix
        # build the K matrix (force)
        # K=np.diag([kinter,kintra])
        # assumes x_init=0.0 # general
        lengths=np.matrix([spr.xeq for spr in springs]).T
        verts=set([idx for spr in springs for idx in spr.ids]) # careful with definition
        adjacency=np.matrix(np.zeros(shape=(len(springs),max(verts)+1))) # careful with definition
        for idx,spr in enumerate(springs):
            adjacency[idx,spr.id2]=1
            adjacency[idx,spr.id1]=-1

        forces=np.matrix(np.diag([spr.force for spr in springs]))
        right_term=adjacency.T*forces*lengths
        left_term=adjacency.T*forces*adjacency
        left_term=left_term[1:,1:]
        right_term=right_term[1:,:]
        try:
            equil=(np.linalg.inv(left_term)*right_term).T[0,:].tolist()[0] # type: ignore
        except np.linalg.linalg.LinAlgError: # type: ignore
            print("raised")
            return None
        return equil # returns x2,x3,...

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
        self.intra:List[Spring]=kwa.get("intra",[])
        self.inter:Dict[int,List[Spring]]=kwa.get("inter",{})

    def __call__(self,*args,**kwa):
        'testing a cleaner __call__'
        state=args[0]
        springs=list(self.intra)+self.used_springs(self.inter,state)
        return self.score_springs(springs,state)

    @staticmethod
    def score_springs(springs,state):
        'adds the energy of all springs'
        scores=[spr.energy(state[spr.id1],state[spr.id2]) for spr in springs]
        return sum(scores)


    @staticmethod
    def used_springs(inter,state)->List[Spring]:
        'returns the spring used for a particular state'
        springs:List[Spring]=[]
        argmax=np.argmax(state)
        # there could be a mistake in the calculus of the score
        # or in the number of springs in inter
        for id1 in inter.keys():
            if id1!=argmax:
                try:
                    scores=sorted([(spr.energy(state[id1],state[spr.id2]),spr)
                                   for spr in inter[id1]],key=lambda x:x[0])
                    springs.append(scores[0][1])
                except IndexError:
                    # for small number of oligos it is possible that
                    # one does not overlap with any other
                    pass

        return springs

    # @staticmethod
    # def potential(rad:np.array)->float:
    #     'Lennard-Jones potential'
    #     return sum((1.1/rad)**12-2*(1.1/rad)**6)

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
        self.scoring=SpringScore(intra=self.intra,
                                 inter=self.inter,
                                 **kwa)
        self.minimizer=SpringMinimizer(intra=self.intra,
                                       inter=self.inter)
        self.res:List[OptimizeResult]=[]
        self.peakid:int=kwa.get("peakid",0) # id of peak to update
        self.basinkwa={"func":self.scoring,
                       "niter":100,
                       "minimizer_kwargs":dict(method=self.minimizer),
                       "take_step":self.stepper}

        # self.basinkwa["minimizer_kwargs"]=dict(method=no_minimizer)
        # self.basinkwa["minimizer_kwargs"]=dict(method="L-BFGS-B")
        # minimization using L-BFGS-B also allows for minimization of vertices


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
        'add springs between oligos of different experiments'
        signs=(0,0) if self.unsigned else (1,1)
        inter:Dict[int,List[Spring]]={idx:[] for idx in range(len(self._olis))}
        for id1,id2 in itertools.permutations(range(len(self._olis)),2):
            if data.Oligo.overlap(self._olis[id1].seq,
                                  self._olis[id2].seq,
                                  min_overl=self.min_overl,
                                  signs=signs,
                                  shift=1):
                inter[id1].append(Spring(type="inter",
                                         force=self.kinter,
                                         xeq=1.1,
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
            print(f"job fun={curr_res.fun}")
            LOGS.debug(f"job fun={curr_res.fun}")
            self.res.append(curr_res)
            state=curr_res.x

        return state

    def order(self,state)->List[data.Oligo]:
        'returns the ordered list of oligos according to state'
        order=sorted([(state[idx],self._olis[idx]) for idx in range(len(self._olis))],
                     key=lambda x:x[0])
        return [oli[1] for oli in order]
