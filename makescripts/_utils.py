#!/usr/bin/env python3
# encoding: utf-8
"The list of modules"
from   pathlib          import Path
from   contextlib       import contextmanager

from   waflib.Build     import BuildContext
from   waflib.Configure import ConfigurationContext

import wafbuilder

BaseContext = BuildContext if Path('../build/c4che').exists() else ConfigurationContext

class Modules:
    "sets-up the modules"
    def __init__(self):
        wafbuilder.defaultwscript("src", "make(locals())")
        self._all = ('tests',) + tuple(wafbuilder.wscripted("src"))

    def addbuild(self, locs):
        "adds build methods"
        wafbuilder.addbuild(self._all, locs)

    def __call__(self, bld):
        "returns the required modules"
        defaults  = getattr(bld.env, 'modules', tuple())
        if bld.options.dyn is True or defaults is None or len(defaults) == 0:
            names = {val.split('/')[-1]: val for val in self._all}

            bld.options.all_modules = names
            bld.env.modules         = tuple()
            if len(bld.options.app):
                vals = tuple(names[i] for i in bld.options.app.split(','))
                bld.recurse(vals, 'defaultmodules', mandatory = False)

            defaults = bld.env.modules
            if len(defaults) == 0:
                defaults = self._all
            else:
                print("Selected modules:", defaults)

        requested = bld.options.modules
        if requested is None or len(requested) == 0:
            mods = defaults
        else:
            mods = tuple(names[req] for req in requested.split(',') if req in names)

        wafbuilder.requirements.reload(('',)+tuple(mods))
        return mods

    @contextmanager
    def options(self, opt):
        "adds options for selecting modules"
        opt.recurse(self._all)
        yield
        opt.add_option('--mod',
                       dest    = 'modules',
                       default = '',
                       action  = 'store',
                       help    = u"modules to build")
        opt.add_option('--dyn',
                       dest    = 'dyn',
                       action  = 'store_true',
                       default = None,
                       help    = (u"consider only modules which were here"
                                  +u" when configure was last launched"))
        opt.add_option('--app',
                       dest    = 'app',
                       action  = 'store',
                       default = '',
                       help    = (u"consider only modules which are "
                                  +u" necessary for provided applications"))

    @contextmanager
    def configure(self, cnf):
        "sets-up modules"
        cnf.env.app = cnf.options.app.split(',') if len(cnf.options.app) else []

        if cnf.options.dyn is None and len(cnf.options.modules) == 0:
            cnf.env.modules = tuple()
            mods            = self(cnf)
        else:
            cnf.env.modules = self(cnf)
            mods            = cnf.env.modules

        yield

        cnf.recurse(mods)

MODULES = Modules()
__all__ = ['MODULES']
