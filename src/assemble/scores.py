#!/usr/bin/env python3
# -*- coding: utf-8 -*-

u'''
defines a list of scoring functors for sequence assembly
'''

class DefaultCallable:
    u'defines a Default Callable'
    def __init__(self,res):
        self.res=res
    def __call__(self,*args,**kwargs):
        u'returns res'
        return self.res


class OverlapDensity:
    u'returns a tuple # of overlaps'
    def __call__(self):
        pass
