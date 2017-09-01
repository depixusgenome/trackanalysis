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
#import random
import networkx
import numpy as np
import scipy.stats
from scipy.optimize import OptimizeResult #basinhopping,
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
        self._fpos:np.array=np.empty(shape=(0,),dtype='f4') # flat
        self._seqs:List[Tuple[str, ...]]=[]
        self._fseqs:List[str]=[] # flat
        self._peaks:List[scaler.OPeakArray]=[]
        self.min_overl:int=kwa.get("min_overl",2)
        self.unsigned:bool=kwa.get("unsigned",True)

    def set_peaks(self,value:scaler.OPeakArray):
        'update peaks and inner attr'
        self._peaks=value
        self._pos=[peak.posarr for peak in value]
        self._fpos=np.array([pos for peak in value for pos in peak.posarr])
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

    # def energy_from_array(self,arr:np.array):
    #     return self.energy(arr[self.id1],arr[self.id2])

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
        self.kintra:float=kwa.get("kintra",1)
        self.kinter:float=kwa.get("kinter",2)
        super().__init__(**kwa)
        self._olis:List[data.OligoPeak]=[]
        self.springs:List[Spring]=[]
        self.peakids:List[List[int]]=[]
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
        self.peakids=[[self._olis.index(oli) for oli in peak.arr]
                      for peak in self.peaks] # not great imp.
        self.springs=[]
        for pkids in self.peakids:
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

class SpringStep(SpringSetting):
    '''
    each moves consists of two steps for each experiment
    a move of all oligos within a peak
    a move for each oligos
    '''
    def __init__(self,**kwa):
        super().__init__(**kwa)
        self.poserr:float=kwa.get("poserr",3.0)
        scale=0.5 # large scale for stretch
        loc=1.0
        # strelower=self.bstretch.lower
        # streupper=self.bstretch.upper
        #scipy.stats.truncnorm(a=(Min-loc)/scale,b=(Max-loc)/scale,loc=loc,scale=scale)
        # self.stredist=scipy.stats.truncnorm(a=(strelower-loc)/scale,
        #                                     b=(streupper-loc)/scale,
        #                                     loc=loc,scale=scale).rvs
        self.stredist=scipy.stats.norm(loc=loc,scale=scale).rvs
        self.biasdist=scipy.stats.uniform(loc=self.bbias.lower,
                                          scale=self.bbias.upper-self.bbias.lower).rvs
        self.noise=scipy.stats.norm(loc=0.,
                                    scale=self.poserr).rvs

    # too long! use matrix notation?
    def __call__(self,*args):
        '''
        draw from self.stredist and self.biasdista
        then apply to original position
        '''
        #npos=self._fpos.copy()
        #npos=np.empty(shape=(0,),dtype='f4')
        arrs:List=[]
        for pkid in self.peakids:
            ones=np.ones(shape=(len(pkid),))
            stre=self.stredist()
            bias=self.biasdist()
            arrs.append(stre*ones+bias)
        noise=self.noise(size=len(self._fpos))

        return noise+np.hstack(arrs)

class SpringScore(SpringSetting):
    '''
    uses springs to scale experiments
    '''
    # def __init__(self,**kwa):
    #     super().__init__(**kwa)


# to rewrite
# class SpringScaler(PeakSetting):
#     '''
#     k_intra, a tension between oligos in the same peak
#     k_extra, a directed tension between oligos which may overlap

#     k_intra allows for gaussian noise around each oligo
#     k_extra necessary to rescale peaks
#     '''
#     def __init__(self,**kwa):
#         super().__init__(**kwa)
#         self.scoring=Score(**kwa)
#         self.sampler=SeqUpdate(**kwa)
#         self.min_overl:int=kwa.get("min_overl",2)
#         self.basinkwa={"func":self.scoring,
#                        "niter":100,
#                        "minimizer_kwargs":dict(method=no_minimizer),
#                        "take_step":self.sampler}
#         self.res:List[OptimizeResult]=[]

#     @property
#     def bstretch(self):
#         'bstretch'
#         return self.sampler.bstretch

#     @property
#     def bbias(self):
#         'bbias'
#         return self.sampler.bbias

#     def run(self):
#         '''
#         simple and naive approach first
#         Consider peaks[0] fixed and only the peaks (1 by 1?) which can overlap with peaks[0]
#         then add others
#         '''
#         biasdist=scipy.stats.uniform(loc=self.bbias.lower,
#                                      scale=self.bbias.upper-self.bbias.lower)
#         stredist=scipy.stats.uniform(loc=self.bstretch.lower,
#                                      scale=self.bstretch.upper-self.bstretch.lower)
#         bias=biasdist.rvs(size=len(self._peaks)-1)
#         stre=stredist.rvs(size=len(self._peaks)-1)
#         state=np.array([1,0]+[val for pair in zip(stre,bias) for val in pair])

#         for loop in itertools.repeat(range(len(self.peaks)),5): # trying to move peaks[0]
#             for lidx in loop:
#         # for _ in range(5):
#         #     loop=np.random.permutation(range(len(self.peaks))) # trying to move peaks[0]
#             # for lidx in loop:
#                 self.sampler.indices=list(self.neigh[lidx])
#                 curr_res=basinhopping(x0=state,**self.basinkwa)
#                 print(f"fun={curr_res.fun}")
#                 self.res.append(curr_res)
#                 state=curr_res.x

#         return state
