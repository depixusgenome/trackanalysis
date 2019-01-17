#!/usr/bin/env python3
# encoding: utf-8
"basic configuration"
from waflib.Build   import BuildContext
import wafbuilder
from ._utils import MODULES

locals().update({i: j for i, j in MODULES.simple('../build/').items()
                 if i in ('requirements', 'tests', 'options')})

def configure(cnf):
    "configure wafbuilder"
    cnf.load('msvs')
    cnf.find_program("sphinx-build", var="SPHINX_BUILD", mandatory=False)
    cnf.env.append_unique('INCLUDES',  ['../../core'])
    MODULES.run_configure(cnf)

def build(bld, mods = None):
    "compile sources"
    if mods is None:
        mods = MODULES(bld)
    bld.build_python_version_file()
    MODULES.build_static()
    bld.add_group('bokeh', move = False)
    wafbuilder.build(bld) # pylint: disable=no-member
    wafbuilder.findpyext(bld, set(mod for mod in mods if mod != 'tests'))
    bld.recurse(mods, 'build')

def linting(bld):
    "display linting info"
    MODULES.check_linting()
