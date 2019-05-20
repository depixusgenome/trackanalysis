#!/usr/bin/env python3
# encoding: utf-8
"wscript cut into pieces"
from pathlib import Path
try:
    from wafbuilder import (
        _utils, findpyext,
        make    as _make,
        default as _default,
        build as _build
    )
    from wafbuilder.apppackager   import package
    from wafbuilder.bokehcompiler import GuiMaker
    from wafbuilder.modules       import Modules, basecontext

except ImportError as exc:
    raise ImportError("Don't forget to clone wafbuilder!!") from exc
_default('python', 'coffee')

_utils.INCORRECT.append(str(Path(__file__).parent))
_utils.ROOT      = str(Path(__file__).parent.parent)
_utils.DEFAULT   = str(Path(__file__).parent.parent/"wscript")


MODULES     = Modules(src = ['core', 'src'])
EXCLUDED    = "tests", "testutils", 'scripting', 'daq'

locals().update(MODULES.simple().items())

def configure(cnf):
    "configure wafbuilder"
    cnf.load('msvs')
    cnf.find_program("sphinx-build", var="SPHINX_BUILD", mandatory=False)
    MODULES.run_configure(cnf)
    cnf.env.append_unique('INCLUDES',  ['../../core'])

def build(bld, mods = None):
    "compile sources"
    if mods is None:
        mods = MODULES(bld)
    bld.build_python_version_file()
    MODULES.build_static(bld)
    bld.add_group('bokeh', move = False)
    _build(bld) # pylint: disable=no-member
    findpyext(bld, list(set(mods)-set(EXCLUDED)))
    bld.recurse(mods, 'build')

def linting(bld):
    "display linting info"
    MODULES.check_linting(bld)

def guimake(viewname, locs, scriptname = None):
    "default make for a gui"
    _make(locs)
    GuiMaker.run(
        viewname, locs, scriptname,
        modules     = ('taskview.toolbar', 'undo'),
        modulepaths = ('core/app', 'core/view'),
        cmdlines    = (
            (r'taskapp/cmdline.pyc --port random -g app ',      False),
            (r'taskapp/cmdline.pyc --port random -g browser ',  True),
        )
    )

locals().update(package(
    MODULES,
    excluded      = EXCLUDED,
    libname       = "trackanalysis",
    resourcepaths = ["makescripts/"+i for i in ("index.gif", "application.desktop")],
    appdir        = "taskapp"
))

__builtins__['guimake'] = guimake # type: ignore
