#!/usr/bin/env python3
# encoding: utf-8
"wscript cut into pieces"
from pathlib import Path
try:
    from wafbuilder import (
        _utils, findpyext,
        make    as _make,
        default as _default,
        build   as _build
    )
    from wafbuilder.modules       import globalmake

except ImportError as exc:
    raise ImportError("Don't forget to clone wafbuilder!!") from exc
_default('python', 'nodejs')

_utils.INCORRECT.append(str(Path(__file__).parent))
_utils.ROOT      = str(Path(__file__).parent.parent)
_utils.DEFAULT   = str(Path(__file__).parent.parent/"wscript")

MODULES  = globalmake(
    locals(),
    src         = ['core', 'src'],
    apppackager = True,
    cmds        = (
        (r'taskapp/cmdline.pyc --port random -g app ',      False),
        (r'taskapp/cmdline.pyc --port random -g browser ',  True),
    ),
    modules     = ('taskview.toolbar', 'undo'),
    jspaths     = ('core/app', 'core/view'),
    resources   = ("makescripts/index.gif", "makescripts/application.desktop"),
)
EXCLUDED = "tests", "testutils", 'scripting', 'daq'

def build(bld, mods = None):
    "compile sources"
    if mods is None:
        mods = MODULES(bld)
    bld.build_appenv()
    _build(bld) # pylint: disable=no-member
    findpyext(bld, list(set(mods)-set(EXCLUDED)))
    bld.recurse(mods, 'build')

def linting(bld):
    "display linting info"
    MODULES.check_linting(bld)
