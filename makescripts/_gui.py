#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Compiles the JS code once and for all"
from pathlib    import Path
from wafbuilder import copyroot, make

def build_bokehjs(bld, *modules):
    "compiles the bokeh js code"
    srcs  = sum((bld.path.ant_glob(i+'/**/*.coffee')
                 for i in {j.split('.')[0] for j in modules}), [])
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

        for i in (bld.path.parent.ant_glob('view/**/*.py')
                  +bld.path.parent.ant_glob('app/**/*.py')):
            i = i.srcpath()
            if Path(str(i)).name[:2] != '__':
                modules.append(str(i)[4:-3].replace("/", ".").replace("\\", "."))
        build_bokehjs(bld, *(i for i in modules if i[:2] != '__'), 'undo')

    locs['build'] = build

__all__ = ['guimake', 'build_bokehjs']
