#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Compiles the JS code once and for all"
from wafbuilder import copyroot, make

def build_bokehjs(bld, module):
    "compiles the bokeh js code"
    srcs  = bld.path.ant_glob('**/*.coffee')
    srcs += bld.path.parent.ant_glob('view/**/*.coffee')
    srcs += bld.path.parent.ant_glob('app/**/*.coffee')
    tgt   = copyroot(bld, module+'.js')
    bld(source      = srcs,
        name        = module+':bokeh',
        color       = 'BLUE',
        rule        = '../makescripts/bokehcompiler.py '+module+' -o ${TGT}',
        target      = tgt,
        cls_keyword = lambda _: 'Bokeh',
        group       = 'bokeh')

def guimake(viewname, locs):
    "default make for a gui"
    make(locs)

    if 'startscripts' not in locs:
        def startscripts(bld):
            "creates start scripts"
            bld.make_startup_script(locs['APPNAME'], locs['APPNAME']+'.'+viewname)
        locs['startscripts'] = startscripts

    old = locs.pop('build')
    def build(bld):
        "build gui"
        old(bld)
        build_bokehjs(bld, locs['APPNAME'])

    locs['build'] = build

__all__ = ['guimake', 'build_bokehjs']
