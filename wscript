#!/usr/bin/env python3
# encoding: utf-8
from makescripts import *

require(cxx    = {'msvc'     : 14.0,
                  'clang++'  : 3.8,
                  'g++'      : 5.4},
        rtime = False)

require(python = {'python': '3.6.3', 'numpy': '1.11.2', 'pandas': '0.19.0'},
        rtime  = True)

require(python = {'pybind11' : '2.2.1',
                  'pylint'   : '1.7.1',
                  'astroid'  : '1.5.3',
                  'mypy'     : '0.511'},
        rtime  = False)

MODULES.addbuild(locals())
