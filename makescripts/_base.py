#!/usr/bin/env python3
# encoding: utf-8
"basic configuration"
from   waflib.Configure import conf
import wafbuilder
from ._utils import MODULES

def options(opt):
    "create options"
    wafbuilder.load(opt)
    with MODULES.options(opt):
        wafbuilder.options(opt)

def configure(cnf):
    "configure wafbuilder"
    cnf.load('msvs')
    with MODULES.configure(cnf):
        wafbuilder.configure(cnf)

def build(bld, mods = None):
    "compile sources"
    if mods is None:
        mods = MODULES(bld)
    bld.build_python_version_file()
    bld.add_group('bokeh', move = False)
    wafbuilder.build(bld)
    wafbuilder.findpyext(bld, set(mod for mod in mods if mod != 'tests'))
    bld.recurse(mods, 'build')

@conf
def transfer_static_html(bld):
    "transfers static files"
    files = bld.path.ant_glob(['static/*.css', 'static/*.js', 'static/*.map',
                               '*/static/*.css', '*/static/*.js', '*/static/*.map'])
    wafbuilder.copyfiles(bld, 'static', files)
