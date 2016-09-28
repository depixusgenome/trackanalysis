#! /usr/bin/env python
# encoding: utf-8
import os
import builder

APPNAME = 'trackanalyzer'

def options(opt):
    builder.options(opt)
    opt.recurse(builder.wscripted("src"))

def configure(cnf):
    builder.configure(cnf)
    cnf.recurse(builder.wscripted("src"))

def environment(cnf):
    print(cnf.env)

def _allbuilds():
    u"relative path to child wscripts"
    yield from builder.wscripted("src")
    yield 'tests'

def build(bld):
    builder.build(bld)
    for item in _allbuilds():
        bld.recurse(item)

for item in _allbuilds():
    builder.addbuild(item, locals())

builder.addmissing(locals())
