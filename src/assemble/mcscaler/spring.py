#!/usr/bin/env python3
# -*- coding: utf-8 -*-


'''
Defines Spring
'''

from typing import Tuple

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
        # if self.thres>0 and abs(xpos2-xpos1-self.xeq)>self.thres:
        #     return 0
        return self.force*(xpos2-xpos1-self.xeq)**2

    def tension(self,xpos1,xpos2):
        'returns the tension applied on the spring'
        # if self.thres>0 and abs(xpos2-xpos1-self.xeq)>self.thres:
        #     return 0
        return 2*self.force*(xpos2-xpos1-self.xeq)

    @property
    def ids(self)->Tuple[int, ...]:
        "ids"
        return tuple([self.id1,self.id2])
