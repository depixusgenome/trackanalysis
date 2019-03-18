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
    for i, j, k in [
            ('i', 'integration', ('-m', 'integration')),
            ('u', 'unit',        ('-m', 'not integration')),
            ('a', 'all',         ())
    ]:
        grp.add_option(
            f'-{i}', f'--{j}tests',
            help    = f"Run {j} tests",
            default = ("-m", "not integration"),
            dest    = "TEST_GROUP",
            action  = "store_const",
            const   = k
        )
    grp.add_option(
        "--coverage",
        help    = "Run tests with coverage",
        default = False,
        dest    = "TEST_COV",
        action  = "store_true",
    )
    grp.add_option(
        "--coverage",
        help    = "Create coverage",
        default = True,
        dest    = "TEST_COV",
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
    from   pathlib   import Path
    from   importlib import import_module
    os.chdir("build")
    if _.options.TEST_HEADLESS:
        os.environ['DPX_TEST_HEADLESS'] = 'True'
        import_module("tests.testutils.bokehtesting").HEADLESS = True

    cmd = ["tests/", *_.options.TEST_GROUP]
    if not _.options.TEST_COV:
        import_module("pytest").cmdline.main(cmd)
    else:
        omits = ["--omit", 'tests/*.py,*waf*.py,*test*.py']
        cmd   = ["run", *omits, "-m", "pytest"] + cmd
        import_module("coverage.cmdline").main(cmd)
        if not Path("Coverage").exists():
            os.mkdir("Coverage")
        import_module("coverage.cmdline").main(["html", "-i", *omits, "-d", "Coverage"])
