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
    print(cnf)
    print(cnf.env)

def build(bld):
    builder.build(bld)
    bld.recurse(builder.wscripted("src"))
    bld.recurse('tests')

builder.addmissing(locals())
