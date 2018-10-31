#!/usr/bin/env python3
# encoding: utf-8
from makescripts import *

require(cxx    = {'msvc'     : 14.0,
                  'clang++'  : 3.8,
                  'g++'      : 7.3},
        rtime = False)

require(python = {'python': '3.6.4', 'numpy': '1.14.2', 'pandas': '0.21.0'},
        rtime  = True)

require(python = {'pybind11'    : '2.2.1',
                  'pylint'      : '2.1.1',
                  'astroid'     : '2.0.3',
                  'mypy'        : '0.630'},
        rtime  = False)

MODULES.addbuild(locals())
