#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Compiles the JS code once and for all"
from pathlib    import Path
from wafbuilder import copyroot, make

def build_bokehjs(bld, key, *modules):
    "compiles the bokeh js code"
    root = bld.path.ctx.bldnode
    mods = [i.split('.')[0] for i in modules]
    mods = [j for i, j in enumerate(mods) if j not in mods[:i]]
    srcs = sum((root.ant_glob(i.replace('.', '/')+'/**/*.coffee') for i in mods), [])
    tgt  = copyroot(bld, key+'.js')

    cmd  = str(bld.path.ctx.srcnode.find_resource('makescripts/bokehcompiler.py'))
    rule = f'{bld.env["PYTHON"][0]} {cmd} '+' '.join(modules)+' -o ${TGT} -k '+key
    bld(source      = srcs,
        name        = modules[0]+':bokeh',
        color       = 'BLUE',
        rule        = rule,
        target      = tgt,
        cls_keyword = lambda _: 'Bokeh',
        group       = 'bokeh')

def guimake_js(bld, viewname, modules, scriptname):
    "create the js"
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
    build_bokehjs(bld, scriptname, *(i for i in modules if i[:2] != '__'), 'undo')

def guimake_doc(bld, scriptname):
    "create the doc"
    if not (
            'SPHINX_BUILD' in bld.env
            and (Path(str(bld.srcnode))/"doc"/scriptname).with_suffix(".rst").exists()
    ):
        return
    if getattr(bld.options, 'APP_PATH', None) is None:
        target = str(bld.bldnode)+"/doc/"+scriptname
    else:
        target = str(bld.options.APP_PATH)+"/doc"+scriptname

    rule = (
        "${SPHINX_BUILD} "+str(bld.srcnode)+"/doc "+target
        + f" -D master_doc={scriptname} -D project={scriptname}"
    )

    bld(
        rule   = rule,
        source = (
            bld.path.ant_glob(f'doc/{scriptname}/*.rst')
            + bld.path.ant_glob('doc/conf.py')
            + bld.path.ant_glob(f'doc/{scriptname}.rst')),
        target = bld.path.find_or_declare(target+f'/{scriptname}.html')
    )

def guimake(viewname, locs, scriptname = None):
    "default make for a gui"
    make(locs)
    name = locs['APPNAME'] if scriptname is None else scriptname

    if 'startscripts' not in locs:
        def startscripts(bld):
            "creates start scripts"
            bld.make_startup_script(name, locs['APPNAME']+'.'+viewname)
        locs['startscripts'] = startscripts

    old = locs.pop('build')
    def build(bld):
        "build gui"
        old(bld)
        guimake_js(bld, viewname, [locs['APPNAME']], name)
        guimake_doc(bld, name)

    locs['build'] = build

__all__ = ['guimake', 'build_bokehjs']
