#!/usr/bin/env python3
# -*- coding: utf-8 -*-


'''
use mcmc to try to converge to a good set of scales
a score can be the number of overlap between consecutives oligos
how to fix the temperature?
need more efficient sampling of (stretch,bias)
'''

from typing import List, Dict, Tuple, Callable, Iterable, NamedTuple, FrozenSet # pylint: disable=unused-import
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

class BasePeakSetting:
    '''
    regroups information regarding oligo experiments
    '''
    def __init__(self,**kwa):
        self._pos:List[np.array]=[]
        self._fpos:List[np.array]=[] # flat
        self._seqs:List[Tuple[str, ...]]=[]
        self._fseqs:List[str]=[] # flat
        self._peaks:List[scaler.OPeakArray]=[]
        self.min_overl:int=kwa.get("min_overl",2)
        self.unsigned:bool=kwa.get("unsigned",True)

    def set_peaks(self,value:scaler.OPeakArray):
        'update peaks and inner attr'
        self._peaks=value
        self._pos=[peak.posarr for peak in value]
        self._fpos=[pos for peak in value for pos in peak.posarr]
        self._seqs=[peak.seqs for peak in value]
        self._fseqs=[seq for seqs in self._seqs for seq in seqs]


    def get_peaks(self):
        'prop'
        return self._peaks

class PeakSetting(BasePeakSetting):
    '''
    regroups information regarding oligo experiments
    '''
    def __init__(self,**kwa):
        super().__init__(**kwa)
        self.peaks:List[scaler.OPeakArray]=kwa.get("peaks",[])

    @property
    def peaks(self):
        'prop'
        return self.get_peaks

    @peaks.setter
    def peaks(self,value:scaler.OPeakArray):
        self.set_peaks(value)




class Spring:
    'models a spring'
    def __init__(self,**kwa):
        self.type:str=kwa.get("type","")
        self.force:float=kwa.get("force",0)
        self.xeq:float=kwa.get("xeq",0)
        self.id1:int=kwa.get("id1",0)
        self.id2:int=kwa.get("id2",0)
        self.direct:bool=kwa.get("direct",False)

    def energy(self,xpos1,xpos2):
        'returns energy on the spring'
        if self.direct:
            return self.force*(xpos2-xpos1-self.xeq)**2
        return self.force*(abs(xpos2-xpos1)-self.xeq)**2

class ScaleSetting(PeakSetting):
    'adds boundaries information on stretch and bias to PeakSetting'
    def __init__(self,**kwa):
        super().__init__(**kwa)
        self.bstretch:scaler.Bounds=kwa.get("bstretch",scaler.Bounds())
        self.bbias:scaler.Bounds=kwa.get("bbias",scaler.Bounds())

class SpringSetting(ScaleSetting):
    '''
    adds Springs to the peaks
    if the noise is small and we rescale peaks kinter>kintra
    should the inter springs be directed? It should help
    '''
    def __init__(self,**kwa):
        super().__init__(**kwa)
        self.kintra:float=kwa.get("kintra",1)
        self.kinter:float=kwa.get("kinter",2)
        self._olis:List[data.OligoPeak]=[]
        self.springs:List[Spring]=[]
        self._peakids:List[List[int]]=[]
        self.peaks:List[scaler.OPeakArray]=kwa.get("peaks",[])

    @property
    def peaks(self)->List[scaler.OPeakArray]:
        'prop'
        return self.get_peaks()

    @peaks.setter
    def peaks(self,peaks:List[scaler.OPeakArray]):
        'peaks setter'
        self.set_peaks(peaks)
        self._olis=[oli for peak in self.peaks for oli in peak.arr] # arbitrary order
        self._peakids=[[self._olis.index(oli) for oli in peak.arr]
                       for peak in self.peaks] # not great imp.
        self.springs=[]
        for pkids in self._peakids:
            self.springs.extend([Spring(type="intra",
                                        force=self.kintra,
                                        xeq=abs(self._fpos[id1]-self._fpos[id2]),
                                        id1=id1,id2=id2)
                                 for id1,id2 in zip(pkids[:-1],pkids[1:])])
        self.add_inter()

    def add_inter(self)->None:
        'add springs between peaks'
        signs=(0,0) if self.unsigned else (1,1)
        for id1,id2 in itertools.permutations(range(len(self._olis)),2):
            if data.Oligo.overlap(self._olis[id1].seq,
                                  self._olis[id2].seq,
                                  min_overl=self.min_overl,
                                  signs=signs,
                                  shift=1):
                self.springs.append(Spring(type="inter",
                                           force=self.kinter,
                                           xeq=1.1,
                                           id1=id1,id2=id2,
                                           direct=True))
        
def no_minimizer(fun, xinit, *args, **options): # pylint: disable=unused-argument
    '''
    use this minimizer to avoid minimization step in basinhopping
    '''
    return OptimizeResult(x=xinit, fun=fun(xinit), success=True, nfev=1)


# class Score(PeakSetting):
#     '''
#     defines a callable with desired params
#     will have to find maximal score according to relative sign
#     assumes the first oligo has the correct sequence...
#     '''
#     def __init__(self,**kwa):
#         super().__init__(**kwa)
#         self.__func:callable=self.callpass
#         self.min_overl:int=kwa.get("min_overl",2)
#         self.unsigned:bool=kwa.get("unsigned",True)
#         seqs=frozenset().union(*[frozenset(pk.seqs) for pk in self.peaks])
#         self.pairseqs=frozenset([(sq1,sq2)
#                                  for sq1,sq2 in itertools.product(seqs,seqs)
#                                  if data.Oligo.overlap(sq1,
#                                                        sq2,
#                                                        min_overl=self.min_overl,
#                                                        signs=(0,0),
#                                                        shift=1)])
#         # the sequential update without considering all peaks leads to the wrong minima
#         self.__ids:Tuple[int]=kwa.get("ids",tuple(range(len(self.peaks))))

#     def callpass(self,*arg,**kwa):
#         'pass'
#         pass

#     def __call__(self,state:np.array)->float:
#         '''
#         scales self.__pos instead of using Rescale.__call__
#         does not consider the signs of oligos nor the constraints
#         (i.e. over estimate the score)
#         check ergodicity
#         '''
#         npos=[state[2*idx]*self._pos[idx]+state[2*idx+1] for idx in self.__ids]
#         fpos=[pos for ppos in npos for pos in ppos] # flat
#         fseqs=[seq for idx in self.__ids for seq in self._seqs[idx]]
#         # sort seq according to npos
#         seqs=[pseq[1] for pseq in sorted(zip(fpos,fseqs))]
#         return -sum([1 for idx,val in enumerate(seqs[1:]) if (seqs[idx],val) in self.pairseqs])

# class StreBiasStep: # pylint: disable=too-many-instance-attributes
#     'defines the take_step callable'
#     def __init__(self,**kwa):
#         self.bstretch:scaler.Bounds=kwa.get("bstretch",scaler.Bounds())
#         self.bbias:scaler.Bounds=kwa.get("bbias",scaler.Bounds())
#         self.cov:np.array=np.array([1])
#         self.__size:int=1
#         self.size:int=kwa.get("size",1)
#         self.__sample:str=""
#         self.biasdist=self.callpass # type: ignore
#         self.stredist=self.callpass # type: ignore
#         self.sample:str=kwa.get("sample","uniform")

#     def callpass(self,*args,**kwa):
#         'pass'
#         pass

#     @property
#     def size(self):
#         'size'
#         return self.__size
#     @size.setter
#     def size(self,value):
#         self.__size=value
#         self.cov=np.array([1 if idx%2
#                            else 0.1
#                            for idx in range(2*self.__size)])
#     @property
#     def sample(self):
#         'property'
#         return self.__sample

#     @sample.setter
#     def sample(self,stype:str):
#         if stype=="uniform": # read stype from enum instead
#             self.__sample=stype
#             self.biasdist=scipy.stats.uniform(loc=self.bbias.lower,
#                                               scale=self.bbias.upper-self.bbias.lower)
#             self.stredist=scipy.stats.uniform(loc=self.bstretch.lower,
#                                               scale=self.bstretch.upper-self.bstretch.lower)
#         # not bounded..
#         if stype=="normal":
#             self.__sample=stype

#         if stype=="discrete":
#             self.__sample=stype
#             raise NotImplementedError

#         if stype=="sequential":
#             self.__sample=stype
#             raise NotImplementedError

#     def __call__(self,*args,**kwa)->np.array:
#         if self.sample=="uniform":
#             bias=self.biasdist.rvs(size=self.size)
#             stre=self.stredist.rvs(size=self.size)
#             return np.array([val for pair in zip(stre,bias) for val in pair])
#         if self.sample=="normal":
#             dist=scipy.stats.multivariate_normal(mean=args[0],cov=self.cov)
#             return dist.rvs()
#         return np.array([])

class SeqUpdate(PeakSetting):
    '''
    sample more efficiently (stretch,bias) for mcmc
    creates a graph: try to fit peaks starting from peaks[0] and adding more and more neighbors
    # make a graph with indices as nodes (do not use make_graph)
    # use find matches
    # pick at random a peak (except 0)
    # move the oligos of that peak (the move can then be optimised with regard to neighbors)
    Need to find the sets of scales for each peaks which gives a different sequence of peaks
    cyclic iteration didn't work too well. when fitting only 1 peak at a time
    could go back to cyclic when neighbors are considered
    '''
    def __init__(self,**kwa):
        super().__init__(**kwa)
        self.bstretch=kwa.get("bstretch",scaler.Bounds())
        self.bbias=kwa.get("bbias",scaler.Bounds())
        self.cycle=itertools.cycle(list(range(1,len(self.peaks)-1)))
        self.index=kwa.get("index",0) # type: int
        self.indices:List[int]=kwa.get("indices",list(range(len(self.peaks))))
        self.call:Callable=self.multi_update # self.single_update

    # need to consider only the peaks that can be matched
    # no need to recompute the bstretch,bbias function of state if using self._pos[tomove]
    def move_one(self,others:np.array,tomove:int):
        '''
        defines a new stre,bias for a single peak
        position to match are located between others positions
        '''
        shifted=0.5*(others[1:]+others[:-1]) # to avoid multiple overlaps
        moves=scaler.match_peaks(shifted,self._pos[tomove],self.bstretch,self.bbias)
        if len(moves)==0:
            print(f"cant move index={tomove}")
        else:
            print(f'can move')
        return random.choice(moves) # type: ignore

    def single_update(self,*args,**kwa): # pylint: disable=unused-argument
        '1 peak has its state updated'
        tomove=self.index
        neigh=sorted(frozenset(self.indices)-frozenset([self.index]))
        state=args[0]
        # scale all peaks
        all_scaled=[state[2*idx]*pos+state[2*idx+1] for idx,pos in enumerate(self._pos)]
        match=np.sort(np.hstack([all_scaled[idx] for idx in neigh]))
        apos=np.sort(np.hstack(all_scaled)) # all positions
        lower=max(apos[apos<min(match)]) if any(apos<min(match)) else min(match)-2.2
        upper=min(apos[apos>max(match)]) if any(apos>max(match)) else max(match)+2.2

        # find where to move
        try:
            #nstre,nbias=self.move_one(match,tomove)
            nstre,nbias=self.move_one(np.hstack([lower,match,upper]),tomove)

        except IndexError:
            return state
        return np.hstack([state[:2*tomove],[nstre,nbias],state[2*(tomove+1):]])

    def __call__(self,*args,**kwa):
        return self.call(*args,**kwa)

    # # fix this: returns only a single update and not all
    def multi_update(self,*args,**kwa)->np.array: # pylint: disable=unused-argument
        '''
        multiple peaks are updated simultaneously
        a peak and overlapping ones
        '''
        self.index=random.choice(self.indices) # type: ignore
        state=args[0]
        # if self.index!=0:
        #    state=self.single_update(state)
        state=self.single_update(state) # trying wth peaks 0 moving
        return state
        
class SpringStep(SpringSetting):
    '''
    each moves consists of two steps for each experiment
    a move of all oligos within a peak
    a move for each oligos
    '''
    pass

class SpringScore(SpringSetting):

    def __init__(self,**kwa):
        super().__init__(**kwa)
        self.edges=scaler.OPeakArray.list2edgeids(self._peaks,
                                                  min_overl=self.min_overl,
                                                  unsigned=self.unsigned)
        self.neigh:Dict[int,List[int]]={idx:frozenset(edg
                                                      for edge in self.edges
                                                      for edg in edge
                                                      if idx in edge)
                                        for idx in range(len(self.peaks))}
        self.springs:Dict[int,Spring]=dict()


class SpringScaler(PeakSetting):
    '''
    k_intra, a tension between oligos in the same peak
    k_extra, a directed tension between oligos which may overlap

    k_intra allows for gaussian noise around each oligo
    k_extra necessary to rescale peaks
    '''
    def __init__(self,**kwa):
        super().__init__(**kwa)
        self.scoring=Score(**kwa)
        self.sampler=SeqUpdate(**kwa)
        self.min_overl:int=kwa.get("min_overl",2)


        # self.edges=scaler.OPeakArray.list2edgeids(self._peaks,
        #                                           min_overl=self.min_overl,
        #                                           unsigned=self.scoring.unsigned)
        # self.neigh:Dict[int,List[int]]={idx:frozenset(edg
        #                                               for edge in self.edges
        #                                               for edg in edge
        #                                               if idx in edge)
        #                                 for idx in range(len(self.peaks))}
        #self.edges=[edge for edge in self.edges if edge[0]<edge[1]]
        self.basinkwa={"func":self.scoring,
                       "niter":100,
                       "minimizer_kwargs":dict(method=no_minimizer),
                       "take_step":self.sampler}
        self.res:List[OptimizeResult]=[]

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

        for loop in itertools.repeat(range(len(self.peaks)),5): # trying to move peaks[0]
            for lidx in loop:
        # for _ in range(5):
        #     loop=np.random.permutation(range(len(self.peaks))) # trying to move peaks[0]
            # for lidx in loop:
                self.sampler.indices=list(self.neigh[lidx])
                curr_res=basinhopping(x0=state,**self.basinkwa)
                print(f"fun={curr_res.fun}")
                self.res.append(curr_res)
                state=curr_res.x

        return state
