#!/usr/bin/env python3
# encoding: utf-8
from pathlib import Path
try:
    import wafbuilder as builder
except ImportError:
    raise ImportError("Don't forget to clone wafbuilder!!")
import wafbuilder.git as git
from waflib.Build       import BuildContext, Context
from waflib.Configure   import ConfigurationContext

require(cxx    = {'msvc'     : 14.0,
                  'clang++'  : 3.8,
                  'g++'      : 5.4},
        rtime = False)

require(python = {'python': 3.5, 'numpy': '1.11.2', 'pandas': '0.19.0'},
        rtime  = True)

require(python = {'pybind11' : '2.1.0',
                  'pylint'   : '1.6.4',
                  'astroid'  : '1.4.8',
                  'mypy'     : '0.470'},
        rtime  = False)


builder.defaultwscript("src", "make()")
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

    requested = bld.options.modules
    if requested is None or len(requested) == 0:
        mods = defaults
    else:
        mods = tuple(names[req] for req in requested.split(',') if req in names)

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
    cnf.load('msvs')
    cnf.env.app = cnf.options.app.split(',') if len(cnf.options.app) else []

    if cnf.options.dyn is None and len(cnf.options.modules) == 0:
        cnf.env.modules = tuple()
        mods            = _getmodules(cnf)
    else:
        cnf.env.modules = _getmodules(cnf)
        mods            = cnf.env.modules

    builder.configure(cnf)
    cnf.recurse(mods)

def build(bld, mods = None):
    if mods is None:
        mods = _getmodules(bld)
    bld.build_python_version_file()
    builder.build(bld)
    builder.findpyext(bld, set(mod for mod in mods if mod != 'tests'))
    bld.recurse(mods, 'build')

class _Test(BuildContext):
    fun = cmd = 'test'
def test(bld):
    u"runs pytests"
    mods  = ('/'+i.split('/')[-1] for i in _getmodules(bld))
    names = (path for path in bld.path.ant_glob(('tests/*test.py', 'tests/*/*test.py')))
    names = (str(name) for name in names if any(i in str(name) for i in mods))
    builder.runtest(bld, *(name[name.rfind('tests'):] for name in names))

def environment(cnf):
    u"prints the environment variables for current configuration"
    print(cnf.env)

class _Requirements(BuildContext if Path('build/c4che').exists() else ConfigurationContext):
    fun = cmd = 'requirements'

def requirements(cnf):
    u"prints requirements"
    _getmodules(cnf)
    builder.requirements.tostream()

class _CondaEnv(BuildContext):
    fun = cmd = 'condaenv'
def condaenv(cnf):
    u"prints the conda yaml recipe"
    _getmodules(cnf)
    builder.condaenv('trackanalysis')

class _CondaSetup(BuildContext if Path('build/c4che').exists() else ConfigurationContext):
    fun = cmd = 'setup'
def setup(cnf):
    u"prints requirements"
    _getmodules(cnf)
    builder.condasetup(cnf)
    print('********************************************')
    print('********************************************')
    print("BOOST must be installed manually")
    if builder.os.sys.platform.startswith("win"):
        print("COFFEESCRIPT is not mandatory & can be installed manually")
    print('********************************************')
    print('********************************************')

class _CondaApp(BuildContext):
    fun = cmd = 'app'
def app(bld):
    bld.options.APP_PATH = bld.bldnode.make_node("output")

    if bld.options.APP_PATH.exists():
        bld.options.APP_PATH.delete()

    build(bld, [i for i in _getmodules(bld) if i != 'tests'])
    builder.condasetup(bld, copy = 'build/output', runtimeonly = True)

    iswin = builder.os.sys.platform.startswith("win")
    ext   = ".bat"                       if iswin else ""
    cmd   = r"start /min %~dp0pythonw " if iswin else "./"

    for name, val in {'cyclesplot': 'cyclesplot.CyclesPlotView'}.items():
        with open(str(bld.options.APP_PATH.make_node(name+ext)), 'w',
                  encoding = 'utf-8') as stream:
            print(cmd + r"app/runapp.py " + val, file = stream)
