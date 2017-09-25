#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Compiles the JS code once and for all"
from pathlib    import Path
from wafbuilder import copyroot, make

def build_bokehjs(bld, *modules):
    "compiles the bokeh js code"
    root = bld.path.ctx.srcnode
    mods = [i.split('.')[0] for i in modules]
    mods = [j for i, j in enumerate(mods) if j not in mods[:i]]
    srcs = sum((root.ant_glob('src/'+i.replace('.', '/')+'/**/*.coffee') for i in mods), [])
    tgt  = copyroot(bld, modules[0]+'.js')

    cmd  = str(bld.path.ctx.srcnode.find_resource('makescripts/bokehcompiler.py'))
    bld(source      = srcs,
        name        = modules[0]+':bokeh',
        color       = 'BLUE',
        rule        = f'python {cmd} '+' '.join(modules)+' -o ${TGT}',
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
        modules = []
        for i in (bld.path.parent.ant_glob(locs['APPNAME']+'/**/*.py')
                  +bld.path.parent.ant_glob('view/**/*.py')
                  +bld.path.parent.ant_glob('app/**/*.py')):
            i = str(i.srcpath())
            if Path(i).name[:2] != '__':
                cur = (i[4:-3].replace("/", ".").replace("\\", ".")).split('.')
                modules.extend('.'.join(cur[:k]) for k in range(1, len(cur)+1))

        modules = [locs['APPNAME']]+list(set(modules) - {''})
        build_bokehjs(bld, *(i for i in modules if i[:2] != '__'), 'undo')

    locs['build'] = build

__all__ = ['guimake', 'build_bokehjs']
