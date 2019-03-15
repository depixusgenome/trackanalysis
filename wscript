#!/usr/bin/env python3
# encoding: utf-8
from makescripts import *

require(cxx    = {'msvc'     : 14.0,
                  'clang++'  : 3.8,
                  'g++'      : 7.3},
        rtime = False)

require(python = {'python': '3.6.4', 'numpy': '1.14.2', 'pandas': '0.21.0'},
        rtime  = True)

require(python = {'pybind11'    : '2.2.1',
                  'pylint'      : '2.1.1',
                  'astroid'     : '2.0.3',
                  'mypy'        : '0.630'},
        rtime  = False)

MODULES.addbuild(locals())

def options(ctx, __old__ = locals().pop('options')):
    "add options"
    __old__(ctx)
    grp = ctx.add_option_group('Test options')
    grp.add_option(
        "--it",
        help    = "Run integration tests only",
        default = False,
        dest    = "TEST_INTEGRATION",
        action  = "store_true",
    )
    grp.add_option(
        "--noheadless",
        help    = "Run browsers in without headless mode",
        default = False,
        dest    = "TEST_HEADLESS",
        action  = "store_false",
    )

def test(_):
    "do unit tests"
    import os
    from   pytest import cmdline
    os.chdir("build")
    if _.options.TEST_HEADLESS:
        from importlib import import_module
        import_module("tests.testutils.bokehtesting").HEADLESS = True
    cmdline.main([
        "tests/",
        "-m",
        ('' if _.options.TEST_INTEGRATION else 'not ')+'integration',
    ])
