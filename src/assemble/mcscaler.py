#!/usr/bin/env python3
# -*- coding: utf-8 -*-


'''
Try to align the different experiments using a random sampling method
Later optimise using MCMC type convergence algorithm
need to define a score for aligning experiments

use mcmc to try to converge to a good set of scales
a score can be the number of overlap between consecutives oligos
how to fix the temperature?

'''



from typing import List, Tuple # pylint: disable=unused-import
import pickle
import itertools
import networkx
import numpy
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



def no_minimizer(fun, xinit, *args, **options): # pylint: disable=unused-argument
    '''
    use this minimizer to avoid minimization step in basinhopping
    '''
    return OptimizeResult(x=xinit, fun=fun(xinit), success=True, nfev=1)


class Score: # pylint: disable=too-many-instance-attributes
    'defines a callable with desired params'
    def __init__(self,**kwa):
        self.__pos=[] # type: List[numpy.array]
        self.__seqs=[] # type: List[Tuple[str, ...]]
        self.__fseqs=[] # type: List[str] # flat
        self.__peaks=[] # type: List[scaler.OPeakArray]
        self.peaks=kwa.get("peaks",[]) # type: List[scaler.OPeakArray]

        self.__min_overl=0
        self.__func=self.callpass # type: Callable
        self.min_overl=kwa.get("min_overl",2)
        self.unsigned=kwa.get("unsigned",True)

    def callpass(self,*arg,**kwa):
        'pass'
        pass

    @property
    def min_overl(self):
        'min_overl'
        return self.__min_overl
    @min_overl.setter
    def min_overl(self,value):
        self.__min_overl=value
        def func(sq1,sq2):
            'score'
            return data.Oligo.overlap(sq1,
                                      sq2,
                                      min_overl=self.__min_overl,
                                      signs=(0,0),
                                      shift=1)
        self.__func=func

    @property
    def peaks(self):
        'prop'
        return self.__peaks

    @peaks.setter
    def peaks(self,value:scaler.OPeakArray):
        'update peaks and inner attr'
        self.__peaks=value
        self.__pos=[peak.posarr for peak in value]
        self.__seqs=[peak.seqs for peak in value]
        self.__fseqs=[seq for seqs in self.__seqs for seq in seqs]

    def __call__(self,state):
        return self.score_state(state)

    def score_state(self,state:numpy.array)->float:
        '''
        scales self.__pos instead of using Rescale.__call__
        '''
        # rescale positions
        npos=[state[2*idx]*pos+state[2*idx+1]
              for idx,pos in enumerate(self.__pos)]
        fpos=[pos for ppos in npos for pos in ppos] # flat

        # sort seq according to npos
        seqs=[pseq[1] for pseq in sorted(zip(fpos,self.__fseqs))]
        return -sum(self.__func(seqs[idx],val) for idx,val in enumerate(seqs[1:]))

class StreBiasStep: # pylint: disable=too-many-instance-attributes
    'defines the take_step callable'
    def __init__(self,**kwa):
        self.bstretch=kwa.get("bstretch",scaler.Bounds())
        self.bbias=kwa.get("bbias",scaler.Bounds())
        self.size=kwa.get("size",1) # type: int
        self.__sample="" # type: str
        self.biasrvs=self.callpass # type: Callable
        self.strervs=self.callpass # type: Callable
        self.sample=kwa.get("sample","uniform") # type: str

    def callpass(self,*args,**kwa):
        'pass'
        pass

    @property
    def sample(self):
        'property'
        return self.__sample

    @sample.setter
    def sample(self,stype:str):
        if stype=="uniform":
            self.__sample=stype
            self.biasrvs=scipy.stats.uniform(loc=self.bbias.lower,
                                             scale=self.bbias.upper-self.bbias.lower).rvs
            self.strervs=scipy.stats.uniform(loc=self.bstretch.lower,
                                             scale=self.bstretch.upper-self.bstretch.lower).rvs
        if stype=="normal":
            raise NotImplementedError

    def __call__(self,*args,**kwa)->numpy.array:
        bias=self.biasrvs(size=self.size)
        stre=self.strervs(size=self.size)
        return numpy.array([val for pair in zip(stre,bias) for val in pair])


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
