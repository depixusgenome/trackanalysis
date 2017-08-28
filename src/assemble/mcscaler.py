#!/usr/bin/env python3
# -*- coding: utf-8 -*-


'''
use mcmc to try to converge to a good set of scales
a score can be the number of overlap between consecutives oligos
how to fix the temperature?
need more efficient sampling of (stretch,bias)
'''

from typing import List, Tuple, Callable # pylint: disable=unused-import
import pickle
import itertools
import random
import networkx
import numpy as np
import scipy.stats
from scipy.optimize import basinhopping, OptimizeResult
import assemble.data as data
import assemble.scaler as scaler

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


class PeakSetting:
    '''
    regroups information regarding oligo experiments
    '''
    def __init__(self,**kwa):
        self._pos=[] # type: List[np.array]
        self._seqs=[] # type: List[Tuple[str, ...]]
        self._fseqs=[] # type: List[str] # flat
        self._peaks=[] # type: List[scaler.OPeakArray]
        self.peaks=kwa.get("peaks",[]) # type: List[scaler.OPeakArray]
        self.min_overl=kwa.get("min_overl",2)
        self.unsigned=kwa.get("unsigned",True)

    @property
    def peaks(self):
        'prop'
        return self._peaks

    @peaks.setter
    def peaks(self,value:scaler.OPeakArray):
        'update peaks and inner attr'
        self._peaks=value
        self._pos=[peak.posarr for peak in value]
        self._seqs=[peak.seqs for peak in value]
        self._fseqs=[seq for seqs in self._seqs for seq in seqs]

def no_minimizer(fun, xinit, *args, **options): # pylint: disable=unused-argument
    '''
    use this minimizer to avoid minimization step in basinhopping
    '''
    return OptimizeResult(x=xinit, fun=fun(xinit), success=True, nfev=1)


class Score(PeakSetting):
    '''
    defines a callable with desired params
    will have to find maximal score according to relative sign
    assumes the first oligo has the correct sequence...
    '''
    def __init__(self,**kwa):
        super().__init__(**kwa)
        self.__func=self.callpass # type: Callable
        self.min_overl=kwa.get("min_overl",2)
        self.unsigned=kwa.get("unsigned",True)
        seqs=frozenset().union(*[frozenset(pk.seqs) for pk in self.peaks])
        self.pairseqs=frozenset([(sq1,sq2)
                                 for sq1,sq2 in itertools.permutations(seqs,2)
                                 if data.Oligo.overlap(sq1,
                                                       sq2,
                                                       min_overl=self.min_overl,
                                                       signs=(0,0),
                                                       shift=1)])
        # change the set of ids to consider for adjusting the mcmc
        self.ids=kwa.get("ids",list(range(len(self.peaks))))

    def callpass(self,*arg,**kwa):
        'pass'
        pass

    def __call__(self,state:np.array)->float:
        '''
        scales self.__pos instead of using Rescale.__call__
        '''
        npos=[state[2*idx]*self._pos[idx]+state[2*idx+1] for idx in self.ids]
        fpos=[pos for ppos in npos for pos in ppos] # flat
        fseqs=[seq for idx in self.ids for seq in self._seqs[idx]]
        # sort seq according to npos
        seqs=[pseq[1] for pseq in sorted(zip(fpos,fseqs))]
        return -sum([1 for idx,val in enumerate(seqs[1:]) if (seqs[idx],val) in self.pairseqs])

class StreBiasStep: # pylint: disable=too-many-instance-attributes
    'defines the take_step callable'
    def __init__(self,**kwa):
        self.bstretch=kwa.get("bstretch",scaler.Bounds())
        self.bbias=kwa.get("bbias",scaler.Bounds())
        self.cov=np.array([1]) # type: np.array
        self.__size=1
        self.size=kwa.get("size",1) # type: int
        self.__sample="" # type: str
        self.biasdist=self.callpass # type: ignore
        self.stredist=self.callpass # type: ignore
        self.sample=kwa.get("sample","uniform") # type: str

    def callpass(self,*args,**kwa):
        'pass'
        pass

    @property
    def size(self):
        'size'
        return self.__size
    @size.setter
    def size(self,value):
        self.__size=value
        self.cov=np.array([1 if idx%2
                           else 0.1
                           for idx in range(2*self.__size)])
    @property
    def sample(self):
        'property'
        return self.__sample

    @sample.setter
    def sample(self,stype:str):
        if stype=="uniform": # read stype from enum instead
            self.__sample=stype
            self.biasdist=scipy.stats.uniform(loc=self.bbias.lower,
                                              scale=self.bbias.upper-self.bbias.lower)
            self.stredist=scipy.stats.uniform(loc=self.bstretch.lower,
                                              scale=self.bstretch.upper-self.bstretch.lower)
        # not bounded..
        if stype=="normal":
            self.__sample=stype

        if stype=="discrete":
            self.__sample=stype
            raise NotImplementedError

        if stype=="sequential":
            self.__sample=stype
            raise NotImplementedError

    def __call__(self,*args,**kwa)->np.array:
        if self.sample=="uniform":
            bias=self.biasdist.rvs(size=self.size)
            stre=self.stredist.rvs(size=self.size)
            return np.array([val for pair in zip(stre,bias) for val in pair])
        if self.sample=="normal":
            dist=scipy.stats.multivariate_normal(mean=args[0],cov=self.cov)
            return dist.rvs()
        return np.array([])



# will not work if any peaks[1:] can't match peaks[0]
# class StreBiasGenerator(PeakSetting):
#     '''
#     sample more efficiently (stretch,bias) for mcmc
#     '''
#     def __init__(self,**kwa):
#         super().__init__(**kwa)
#         self.bstretch=kwa.get("bstretch",scaler.Bounds())
#         self.bbias=kwa.get("bbias",scaler.Bounds())
#         self.noise=scipy.stats.norm(loc=0,scale=0.1).rvs
#         self.matches=[[scale.toarr
#                        for scale in scaler.scale_peaks(self.peaks[0].posarr,
#                                                        peak.posarr,
#                                                        self.bstretch,
#                                                        self.bbias)] for peak in self.peaks[1:]]
#         self.lengths=[len(val) for val in self.matches]



#     def __call__(self,*args,**kwargs):
#         # naive version:
#         # for each peak pick a scale and apply a small random noise on the bias
#         noise=self.noise(size=len(self.peaks[1:]))
#         scales=[match[np.random.randint(self.lengths[idx])]+np.array([0,noise[idx]])
#                 for idx,match in enumerate(self.matches)]
#         return np.array([1,0]+[val for scl in scales for val in scl])


class SeqUpdate(PeakSetting):
    '''
    sample more efficiently (stretch,bias) for mcmc
    creates a graph: try to fit peaks starting from peaks[0] and adding more and more neighbors
    # make a graph with indices as nodes (do not use make_graph)
    # use find matches
    # pick at random a peak (except 0)
    # move the oligos of that peak (the move can then be optimised with regard to neighbors)
    Need to find the sets of scales for each peaks which gives a different sequence of peaks
    '''
    def __init__(self,**kwa):
        super().__init__(**kwa)
        self.bstretch=kwa.get("bstretch",scaler.Bounds())
        self.bbias=kwa.get("bbias",scaler.Bounds())
        self.cycle=itertools.cycle(list(range(1,len(self.peaks)-1)))
        self.index=kwa.get("index",1) # type: int

    def next_move(self,npos:List[np.array],tomove:int):
        'defines a new stre,bias for a single peak'
        others=np.sort(np.hstack(npos[:tomove]+npos[tomove+1:]))
        moves=scaler.match_peaks(others,self._pos[tomove],self.bstretch,self.bbias)
        return random.choice(moves) # type: ignore

    def __call__(self,*args,**kwargs):
        tomove=self.index
        state=args[0]
        # scale all peaks
        npos=[state[2*idx]*arr+state[2*idx+1] for idx,arr in enumerate(self._pos)]
        # find where to move
        try:
            nstre,nbias=self.next_move(npos,tomove)
        except IndexError:
            return state
        return np.hstack([state[:2*tomove],[nstre,nbias],state[2*(tomove+1):]])



class HopperStatus:
    'basinhopping container'
    def __init__(self,**kwa):
        self.state=kwa.get("state",np.array)
        self.scores=[] # type: List[float]

class SeqHoppScaler(PeakSetting):
    '''
    adjust the scales of experiments to minimize scoring function
    Could be better with a full-fledged MCTS implementation
    Controls the SeqUpdate instance together with the Score
    decides which indices must be used to compute the score
    and which index must be updated
    '''
    def __init__(self,**kwa):
        super().__init__(**kwa)
        self.scoring=Score(**kwa)
        self.sampler=SeqUpdate(**kwa)
        self.min_overl=kwa.get("min_overl",2) # type: int
        self.edges=scaler.OPeakArray.list2edgeids(self._peaks,
                                                  min_overl=self.min_overl,
                                                  unsigned=self.scoring.unsigned)
        self.edges=[edge for edge in self.edges if edge[0]<edge[1]]
        self.basinkwa={"func":self.scoring,
                       "niter":100,
                       "minimizer_kwargs":dict(method=no_minimizer),
                       "take_step":self.sampler}
        self.res=[] # type: List[scipy.optimize.optimize.OptimizeResult]

    @property
    def bstretch(self):
        'bstretch'
        return self.sampler.bstretch

    @property
    def bbias(self):
        'bbias'
        return self.sampler.bbias

    def run(self):
        '''
        simple and naive approach first
        Consider peaks[0] fixed and only the peaks (1 by 1?) which can overlap with peaks[0]
        then add others
        '''
        biasdist=scipy.stats.uniform(loc=self.bbias.lower,
                                     scale=self.bbias.upper-self.bbias.lower)
        stredist=scipy.stats.uniform(loc=self.bstretch.lower,
                                     scale=self.bstretch.upper-self.bstretch.lower)
        bias=biasdist.rvs(size=len(self._peaks)-1)
        stre=stredist.rvs(size=len(self._peaks)-1)
        state=np.array([1,0]+[val for pair in zip(stre,bias) for val in pair])

        toscore=[0]
        for edge in self.edges:
            toscore=sorted(frozenset(toscore).union(edge))
            self.scoring.ids=toscore
            # I cannot change only edge[1] but edge[1] and all neighbors
            self.sampler.index=edge[1]
            curr_res=basinhopping(x0=state,**self.basinkwa)
            print(f"fun={curr_res.fun}")
            self.res.append(curr_res)
            state=curr_res.x

        return state
if __name__=='__main__':
    UNSIGNED= True
    MIN_OVERL=2
    BBIAS=scaler.Bounds(-6,6)
    BSTRETCH=scaler.Bounds(0.95,1.05)

    OLIGOS=pickle.load(open("oligos_sd1_os3.pickle","rb"))

    SCA=scaler.SubScaler(oligos=OLIGOS,
                         min_overl=MIN_OVERL,
                         bstretch=BSTRETCH,
                         bbias=BBIAS,
                         posid=0)
    PEAKS=SCA.peaks


    # compute all (strech,bias) that any exp can take when fitting to any other
    # make a graph
    GRAPH=make_graph(PEAKS,BSTRETCH,BBIAS,MIN_OVERL,UNSIGNED)
    # we fix the experiment with maximal number of peaks
    # for each node in graph compute (stretch,bias) possible
    SCALES={(p1,p2):p1.find_matches(p2,BSTRETCH,BBIAS,unsigned=UNSIGNED)
            for p1 in GRAPH.nodes()
            for p2 in networkx.neighbors(GRAPH,p1)
            if p2!=PEAKS[0]}




    SCORING=Score(peaks=PEAKS,min_overl=MIN_OVERL,unsigned=UNSIGNED)
    print("score set")
    STEP=StreBiasStep(bstretch=BSTRETCH,bbias=BBIAS,size=len(PEAKS),sample="uniform")
    STATE_INIT=STEP()
    RESULT=basinhopping(func=SCORING,
                        x0=STATE_INIT,
                        niter=1000,
                        minimizer_kwargs=dict(method=no_minimizer),
                        take_step=STEP)
