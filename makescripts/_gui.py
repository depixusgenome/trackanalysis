#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Compiles the JS code once and for all"
from wafbuilder import copyroot, make

def build_bokehjs(bld, *modules):
    "compiles the bokeh js code"
    srcs  = bld.path.ant_glob('**/*.coffee')
    srcs += bld.path.parent.ant_glob('view/**/*.coffee')
    srcs += bld.path.parent.ant_glob('app/**/*.coffee')
    tgt   = copyroot(bld, modules[0]+'.js')
    bld(source      = srcs,
        name        = modules[0]+':bokeh',
        color       = 'BLUE',
        rule        = '../makescripts/bokehcompiler.py '+' '.join(modules)+' -o ${TGT}',
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
        modules = [locs['APPNAME']]
        if '.' in viewname:
            for i in viewname.split('.'):
                if i[0] == i[0].upper():
                    break
                modules.append(modules[-1]+'.'+i)

        build_bokehjs(bld, *modules)

    locs['build'] = build

__all__ = ['guimake', 'build_bokehjs']
