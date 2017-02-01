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
                  'pylint'   : '1.5.4',
                  'pytest'   : '3.0.4',
                  'mypy'     : '0.4.4'},
        rtime  = False)

class _Tester(BuildContext):
    u"runs pytests"
    cmd = 'test'
    fun = 'test'

_ALL   = ('tests',) + tuple(builder.wscripted("src"))
_RAMPMODS = tuple('src/'+i for i in['data','view','legacy','ramp','model','control'])
for item in _ALL:
    builder.addbuild(item, locals())

def _getmodules(bld):
    defaults  = getattr(bld.env, 'MODULES', tuple())
    if bld.options.dyn is True or defaults is None or len(defaults) == 0:
        defaults = _ALL

    requested = bld.options.modules
    if requested is None or len(requested) == 0:
        mods = defaults

    if bld.options.app is True:
        mods = _RAMPMODS
    else:
        names = {val.split('/')[-1]: val for val in defaults}
        mods  = tuple(names[req] for req in requested.split(',') if req in names)
    
        
    builder.requirements.reload(('',)+tuple(mods))
    return mods

def options(opt):
    builder.load(opt)
    for item in _ALL:
        opt.recurse(item)
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
                   action  = 'store_true',
                   default = False,
                   help    = (u"consider only modules which are "
                              +u" necessary for rampapp"))

def configure(cnf):
    if cnf.options.dyn is None and len(cnf.options.modules) == 0:
        cnf.env.MODULES = tuple()
        mods            = _getmodules(cnf)
    else:
        cnf.env.MODULES = _getmodules(cnf)
        mods            = cnf.env.MODULES

    builder.configure(cnf)
    for item in mods:
        cnf.recurse(item)

def build(bld):
    mods = _getmodules(bld)
    builder.build(bld)
    if len(bld.options.modules):
        print('building:', *mods)

    builder.findpyext(bld, set(mod for mod in mods if mod != 'tests'))
    for item in mods:
        bld.recurse(item)

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
