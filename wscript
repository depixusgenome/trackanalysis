#!/usr/bin/env python3
# encoding: utf-8
import sys
from wafbuilder  import PyTesting
from makescripts import *

require(cxx    = {'msvc'     : 14.0,
                  'clang++'  : 3.8,
                  'g++'      : 7.3},
        rtime = False)

PYVERS         = (
    '3.6.4' if sys.platform.startswith("win") else
    '=3.7.0=hfd72cd7_0=conda-forge'
)

require(python = {'python': PYVERS, 'numpy': '1.14.2', 'pandas': '0.21.0'},
        rtime  = True)

require(python = {'pybind11'    : '2.2.1',
                  'pylint'      : '=2.2.1',
                  'astroid'     : '=2.1.0',
                  'mypy'        : '=0.701'},
        rtime  = False)

MODULES.addbuild(locals())
PyTesting.make(locals())
