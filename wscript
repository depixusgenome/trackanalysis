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

_ALL   = ('tests',) + tuple(builder.wscripted("src"))

def options(opt):
    opt.load('waf_unit_test pytest')
    builder.options(opt)
    opt.add_option('--mod',   dest = 'modules', action = 'store', help=u"modules to build")
    opt.add_option('--nodyn', dest = 'dyn',
                   action  = 'store_false',
                   default = True,
                   help    = (u"consider only modules which were here"
                              +u" when configure was last launched"))
    for item in _ALL:
        opt.recurse(item)

def _get(dyn, base, defaults, requested):
    if len(defaults) == 0 or dyn:
        defaults = base
    if requested is None or len(requested) == 0:
        return defaults

    else:
        names = {val.split('/')[-1]: val for val in defaults}
        return tuple(names[req] for req in requested.split(',') if req in names)

def configure(cnf):
    builder.configure(cnf)
    cnf.env.MODULES = _get(cnf.options.dyn, _ALL, _ALL, cnf.options.modules)
    for item in cnf.env.MODULES:
        cnf.recurse(item)

def build(bld):
    builder.build(bld)

    mods = _get(bld.options.dyn, _ALL, bld.env.MODULES, bld.options.modules)
    if len(mods) < len(bld.env.MODULES if len(bld.env.MODULES) else _ALL):
        print('building:', *mods)

    builder.findpyext(bld, set(mod for mod in mods if mod != 'tests'))
    for item in mods:
        bld.recurse(item)

def environment(cnf):
    u"prints the environment variables for current configuration"
    print(cnf.env)

def condaenv(_):
    u"prints the conda yaml recipe"
    builder.condaenv('trackanalysis')

def requirements(_):
    u"prints requirements"
    builder.requirements()

def test(bld):
    u"runs pytests"
    mods   = _get(bld.options.dyn, _ALL, bld.env.MODULES, bld.options.modules)
    mods   = ('/'+i.split('/')[-1] for i in mods)
    names  = (path for path in bld.path.ant_glob(('tests/*test.py', 'tests/*/*test.py')))
    names  = (str(name) for name in names if any(i in str(name) for i in mods))
    builder.runtest(bld, *(name[name.rfind('tests'):] for name in names))

class Tester(BuildContext):
    u"runs pytests"
    cmd = 'test'
    fun = 'test'

for item in _ALL:
    builder.addbuild(item, locals())
