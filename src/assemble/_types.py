#!/usr/bin/env python3
# -*- coding: utf-8 -*-

u'newtypes for typing'
from abc import ABCMeta, abstractmethod
import scipy.stats



class SciDist(metaclass=ABCMeta):
    u'registers a new type of distribution'
    @abstractmethod
    def rvs(self,*args,**kwargs):
        u'random variable sample'
        pass
    @abstractmethod
    def pdf(self,*_1,**_2):
        u'density function'
        pass



SciDist.register(scipy.stats._distn_infrastructure.rv_frozen) # pylint: disable=no-member,protected-access
