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

def condaenv(cnf):
    builder.condaenv(open('tmp.yaml', "w"), 'trackanalysis')

for item in _ALL:
    builder.addbuild(item, locals())
