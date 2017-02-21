#!/usr/bin/env python3
# encoding: utf-8
from waflib.Build import BuildContext
try:
    import wafbuilder as builder
except ImportError:
    raise ImportError("Don't forget to clone wafbuilder!!")

require(cxx    = {'msvc'     : 14.0,
                  'clang++'  : 3.8,
                  'g++'      : 5.4},
        rtime = False)

require(python = {'python': 3.5, 'numpy': '1.11.2', 'pandas': '0.19.0'},
        rtime  = True)

require(python = {'pybind11' : '2.0.1',
                  'pylint'   : '1.6.4',
                  'astroid'  : '1.4.8',
                  'mypy'     : '0.4.4'},
        rtime  = False)

class _Tester(BuildContext):
    u"runs pytests"
    cmd = 'test'
    fun = 'test'

_ALL      = ('tests',) + tuple(builder.wscripted("src"))
builder.addbuild(_ALL)

def _getmodules(bld):
    defaults  = getattr(bld.env, 'modules', tuple())
    if bld.options.dyn is True or defaults is None or len(defaults) == 0:
        names = {val.split('/')[-1]: val for val in _ALL}

        bld.options.all_modules = names
        bld.env.modules         = tuple()
        if len(bld.options.app):
            vals = tuple(names[i] for i in bld.options.app.split(','))
            bld.recurse(vals, 'defaultmodules', mandatory = False)

        defaults = bld.env.modules
        if len(defaults) == 0:
            defaults = _ALL
        else:
            print("Selected modules:", defaults)

    requested   = bld.options.modules
    if requested is None or len(requested) == 0:
        mods  = defaults
    else:
        mods  = tuple(names[req] for req in requested.split(',') if req in names)

    builder.requirements.reload(('',)+tuple(mods))
    return mods

def options(opt):
    builder.load(opt)
    opt.recurse(_ALL)
    builder.options(opt)

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

def configure(cnf):
    cnf.env.app = cnf.options.app.split(',') if len(cnf.options.app) else []

    if cnf.options.dyn is None and len(cnf.options.modules) == 0:
        cnf.env.modules = tuple()
        mods            = _getmodules(cnf)
    else:
        cnf.env.modules = _getmodules(cnf)
        mods            = cnf.env.modules

    builder.configure(cnf)
    cnf.recurse(mods)

def build(bld):
    mods = _getmodules(bld)
    builder.build(bld)
    builder.findpyext(bld, set(mod for mod in mods if mod != 'tests'))
    bld.recurse(mods)

def test(bld):
    u"runs pytests"
    mods  = ('/'+i.split('/')[-1] for i in _getmodules(bld))
    names = (path for path in bld.path.ant_glob(('tests/*test.py', 'tests/*/*test.py')))
    names = (str(name) for name in names if any(i in str(name) for i in mods))
    builder.runtest(bld, *(name[name.rfind('tests'):] for name in names))

def environment(cnf):
    u"prints the environment variables for current configuration"
    print(cnf.env)

def condaenv(cnf):
    u"prints the conda yaml recipe"
    _getmodules(cnf)
    builder.condaenv('trackanalysis')

def requirements(cnf):
    u"prints requirements"
    _getmodules(cnf)
    builder.requirements.tostream()
