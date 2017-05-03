#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u'Testing'
from utils import initdefaults

class Test:
    u'testclass'
    prec=-1.0 # type: float
    index=-1 # type: int
    @initdefaults
    def __init__(self,prec,index,**kwa):
        pass
