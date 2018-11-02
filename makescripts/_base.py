#!/usr/bin/env python3
# encoding: utf-8
"basic configuration"
from   pathlib          import Path
import wafbuilder
import wafbuilder.git
from ._utils import MODULES

locals().update({i: j for i, j in MODULES.simple('../build/').items()
                 if i in ('requirements', 'tests', 'options')})

def _action(tsk):
    inpt = tsk.inputs[0].abspath()
    if not ("view" in inpt and inpt.endswith(".py")):
        return False

    lines = []
    with open(inpt, "r", encoding="utf-8") as inp:
        lines.extend(inp.readlines())

    chg = [i for i, j in enumerate(lines) if "?v=gittag" in j]
    if chg:
        for i in chg:
            vers = lines[i].split("gittag")
            for j, chunk in enumerate(vers):
                if not chunk.endswith("?v="):
                    continue
                name = chunk[chunk.rfind("/")+1:-3]
                path = Path(inpt).parent /"static"/ name
                if not path.exists():
                    path = path.parent.parent /"static"/ name
                    assert path.exists()
                vers[j] = chunk+wafbuilder.git.lasthash(str(path))
            lines[i] = "".join(vers)

        with open(tsk.outputs[0].abspath(), "w", encoding="utf-8") as out:
            print("".join(lines), file = out)
        return True
    return False

wafbuilder.FILTERS.append(_action)
def configure(cnf):
    "configure wafbuilder"
    cnf.load('msvs')
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
