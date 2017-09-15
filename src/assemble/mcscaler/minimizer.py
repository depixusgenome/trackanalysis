#!/usr/bin/env python3
# -*- coding: utf-8 -*-


'''
defines ways to  minimize the energy and score of a spring system
'''

from typing import List, Dict, Callable
import numpy as np
from scipy.optimize import OptimizeResult
from utils.logconfig import getLogger
from assemble.settings import SpringSetting
from spring import Spring
from scores import SpringScore

LOGS=getLogger(__name__)


class SpringMinimizer(SpringSetting):
    'regroups the different ways to minimize the spring network'
    def __init__(self,**kwa):
        super().__init__(**kwa)
        self.intra:List[Spring]=kwa.get("intra",[])
        self.inter:Dict[int,List[Spring]]=kwa.get("inter",dict())
        method:str=kwa.get("method","bare")
        self.call:Callable=self.__getattribute__(method)

    def __call__(self,*args,**kwa):
        return self.call(self,*args,**kwa)

    def bare(self,_,_2,*args, **kwa): # pylint: disable=unused-argument
        'finds equilibrium of a system of springs'
        springs=list(self.intra)+SpringScore.used_springs(self.inter,args[0])
        return self.equilibrium(springs,args[0])

    def max_overlaps(self,_,_2,*args, **kwa): # pylint: disable=unused-argument
        '''
        finds equilibrium of a system of springs
        returns minus the number of overlaps
        '''
        springs=list(self.intra)+SpringScore.used_springs(self.inter,args[0])
        state=self.equilibrium(springs,args[0]).x
        fun=-SpringScore.noverlaps(oligos=self._olis,
                                   state=state,
                                   unsigned=self.unsigned,
                                   min_overl=self.min_overl)
        return OptimizeResult(x=state,
                              fun=fun,
                              success=True,
                              nfev=1,
                              springs=springs,
                              state_pre_min=args[0])

    @staticmethod
    def equilibrium(springs,xinit)->OptimizeResult:
        'find the equilibrium for a given list of springs and xinit'
        equil=SpringMinimizer.find_equilibrium(springs)

        if equil is None:
            return OptimizeResult(x=xinit,
                                  fun=SpringScore.energy_system(springs,xinit),
                                  success=True,
                                  nfev=1,
                                  springs=springs,
                                  state_pre_min=xinit)

        if len(equil)!=len(xinit)-1:
            print("unconstrained vertex")
            # unconstrained vertex by set of springs
            return OptimizeResult(x=xinit,
                                  fun=SpringScore.energy_system(springs,xinit),
                                  success=True,
                                  nfev=1,
                                  springs=springs,
                                  state_pre_min=xinit)

        equil=xinit[0]+np.array([0.0]+equil)
        # mean conservation
        equil=equil-np.mean(equil)+np.mean(xinit)
        return OptimizeResult(x=equil,
                              fun=SpringScore.energy_system(springs,equil),
                              success=True,
                              nfev=1,
                              springs=springs,
                              state_pre_min=xinit)


    @staticmethod
    def no_minimizer(fun, xinit, *args, **options): # pylint: disable=unused-argument
        '''
        use this minimizer to avoid minimization step in basinhopping
        '''
        return OptimizeResult(x=xinit, fun=fun(xinit), success=True, nfev=1)

    @staticmethod
    def find_equilibrium(springs:List[Spring]):
        '''
        problem when the set of springs does not include all vertices in the system
        solves the SpringSystem
        this function computes the equilibrium, not the minimisation of energy
        '''
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
