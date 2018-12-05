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
    MODULES.run_configure(cnf)

def build(bld, mods = None):
    "compile sources"
    if mods is None:
        mods = MODULES(bld)
    bld.build_python_version_file()
    files = bld.path.ant_glob(["src/**/static/*."+j
                               for j in ("css", "js", "map", "svg", "eot",
                                         "ttf", "woff")])
    wafbuilder.copyfiles(bld, 'static', files)

    bld.add_group('bokeh', move = False)
    wafbuilder.build(bld) # pylint: disable=no-member
    wafbuilder.findpyext(bld, set(mod for mod in mods if mod != 'tests'))
    bld.recurse(mods, 'build')

def linting(bld):
    "display linting info"
    stats: dict = {'count': 0}
    patt        = "pylint: disable="
    for name in bld.path.ant_glob("src/**/*.py"):
        if "scripting" in str(name):
            continue
        mdl = str(name)[len(str(bld.path)+"/src/"):]
        mdl = mdl[:mdl.find('/')]
        with open(str(name), 'r') as stream:
            for line in stream:
                if patt not in line:
                    continue
                stats['count'] += 1
                tpe = line[line.find(patt)+len(patt):].strip()
                if " " in tpe:
                    tpe = tpe[:tpe.find(" ")]
                for i in tpe.split(","):
                    info = stats.setdefault(i, {'count': 0})
                    info ['count'] += 1
                    info.setdefault(mdl, 0)
                    info[mdl] += 1

    print(f"""
        Totals
        =====
        
        count: {stats.pop('count')}
          """)
    for i, j in sorted(stats.items(), key = lambda x: x[1]['count'])[::-1]:
        cnt  = j.pop("count")
        itms = sorted(j.items(), key = lambda k: k[1])[::-1][::5]
        print(f"{str(i)+':':<35}{cnt:>5}\t\t{itms}")
