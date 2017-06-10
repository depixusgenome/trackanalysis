#!/usr/bin/env python3
# encoding: utf-8
"Everything related to tests"
from   waflib.Build     import BuildContext
import wafbuilder
from   ._utils          import MODULES

class _Test(BuildContext):
    fun = cmd = 'test'
def test(bld):
    u"runs pytests"
    mods  = ('/'+i.split('/')[-1] for i in MODULES(bld))
    names = (path for path in bld.path.ant_glob(('tests/*test.py', 'tests/*/*test.py')))
    names = (str(name) for name in names if any(i in str(name) for i in mods))
    wafbuilder.runtest(bld, *(name[name.rfind('tests'):] for name in names))

__all__ = ['test']
