#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Compiles the JS code once and for all"
from pathlib    import Path
from wafbuilder import copyroot, make

def build_bokehjs(bld, *modules):
    "compiles the bokeh js code"
    root = bld.path.ctx.bldnode
    mods = [i.split('.')[0] for i in modules]
    mods = [j for i, j in enumerate(mods) if j not in mods[:i]]
    srcs = sum((root.ant_glob(i.replace('.', '/')+'/**/*.coffee') for i in mods), [])
    tgt  = copyroot(bld, modules[0]+'.js')

    cmd  = str(bld.path.ctx.srcnode.find_resource('makescripts/bokehcompiler.py'))
    bld(source      = srcs,
        name        = modules[0]+':bokeh',
        color       = 'BLUE',
        rule        = f'{bld.env["PYTHON"][0]} {cmd} '+' '.join(modules)+' -o ${TGT}',
        target      = tgt,
        cls_keyword = lambda _: 'Bokeh',
        group       = 'bokeh')

def guimake(viewname, locs, scriptname = None):
    "default make for a gui"
    make(locs)

    if 'startscripts' not in locs:
        def startscripts(bld):
            "creates start scripts"
            name = locs['APPNAME'] if scriptname is None else scriptname
            bld.make_startup_script(name, locs['APPNAME']+'.'+viewname)
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
