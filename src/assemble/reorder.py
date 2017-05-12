#!/usr/bin/env python3
# -*- coding: utf-8 -*-

u'''
given k-permutations, attempts to reconstruct the most likely order of oligohits
kperms, should  not includ neutral operators
'''

from typing import List, Dict, Tuple # pylint: disable=unused-import

from utils import initdefaults
from . import data # pylint: disable=unused-import
from . import scores # needed to estimate the quality of each kperm



class KPermAssessor:
    u'''
    rank the kperms by importance (quality)
    '''
    kperms = [] # type: List[data.OligoPeakKPerm]
    __scorekperm=dict() # type: Dict
    __ranking=[] # type: List[Tuple]
    @initdefaults(frozenset(locals()))
    def __init__(self,**kwa):
        u'''
        oligos is the full list of oligos
        kperms is the list of k-permutations
        '''
        pass

    @property
    def scorekperm(self)->Dict:
        u'score each kperm'
        if self.__scorekperm==dict():
            self.__scorekperm=dict((kpr,scores.ScoreAssembly(assembly=kpr).run())
                                   for kpr in self.kperms)

        return self.__scorekperm

    def scores(self)->List:
        u'apply ScoreAssembly on each of the kperms'
        return [self.scorekperm[kpr] for kpr in self.kperms]

    def ranking(self,reverse=False):
        u'returns sorted [(score,kperm) for kperm in kperms]'
        if self.__ranking==[]:
            self.__ranking=sorted(self.scorekperm.items(),reverse=reverse)
        return self.__ranking
