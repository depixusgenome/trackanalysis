#!/usr/bin/env python3
# encoding: utf-8
import os
import builder

_ALL = ('tests',) + tuple(builder.wscripted("src"))

def _recurse(fcn):
    return builder.recurse(builder, _ALL)(fcn)

def environment(cnf):
    print(cnf.env)

@_recurse
def options(opt):
    pass

@_recurse
def configure(cnf):
    pass

@_recurse
def build(bld):
    builder.findpyext(bld, builder.wscripted('src'))

for item in _ALL:
    builder.addbuild(item, locals())
