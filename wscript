#!/usr/bin/env python3
# encoding: utf-8
try:
    import wafbuilder as builder
except ImportError:
    raise ImportError("Don't forget to clone wafbuilder!!")


require(cxx    = {'msvc'     : 14.0,
                  'clang++'  : 3.8,
                  'g++'      : 5.4},
        rtime = False)

require(python = {'python': 3.5, 'numpy': '1.11.2', 'pandas': '0.19.0'},
        rtime  = True)

require(python = {'pybind11' : '2.0.1',
                  'pylint'   : '1.5.4',
                  'pytest'   : '3.0.4',
                  'mypy'     : '0.4.4'},
        rtime  = False)

_ALL   = ('tests',) + tuple(builder.wscripted("src"))

def options(opt):
    builder.options(opt)
    for item in _ALL:
        opt.recurse(item)

def configure(cnf):
    builder.configure(cnf)
    for item in _ALL:
        cnf.recurse(item)

def build(bld):
    builder.build(bld)
    builder.findpyext(bld, _ALL[1:])
    for item in _ALL:
        bld.recurse(item)

def environment(cnf):
    u"prints the environment variables for current configuration"
    print(cnf.env)

def condaenv(_):
    u"prints the conda yaml recipe"
    builder.condaenv('trackanalysis')

def requirements(_):
    u"prints requirements"
    builder.requirements()

for item in _ALL:
    builder.addbuild(item, locals())
