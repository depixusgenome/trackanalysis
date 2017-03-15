#!/usr/bin/env python3
# encoding: utf-8
from functools import wraps as _wraps
try:
    import wafbuilder as builder
except ImportError:
    raise ImportError("Don't forget to clone wafbuilder!!")
import wafbuilder.git as git
from waflib.Build import BuildContext

require(cxx    = {'msvc'     : 14.0,
                  'clang++'  : 3.8,
                  'g++'      : 5.4},
        rtime = False)

require(python = {'python': 3.5, 'numpy': '1.11.2', 'pandas': '0.19.0'},
        rtime  = True)

require(python = {'pybind11' : '2.0.1',
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

    requested   = bld.options.modules
    if requested is None or len(requested) == 0:
        mods  = defaults
    else:
        mods  = tuple(names[req] for req in requested.split(',') if req in names)

    builder.requirements.reload(('',)+tuple(mods))
    return mods

def _command(fcn):
    loc  = builder.getlocals()
    name = "_"+fcn.__name__.capitalize()
    loc[name] =  type(name, (BuildContext,), dict(cmd = fcn.__name__,
                                                  fun = fcn.__name__))

    @_wraps(fcn)
    def _wrap(bld:BuildContext):
        _getmodules(bld)
        fcn(bld)
    return fcn

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
    lines  = '#!/usr/bin/env python3\n'
    lines += '# encoding: utf-8\n'
    lines += 'u"Build information"'
    lines += '\n'
    lines += 'def version ():\n    u"git version"\n    return "%s"\n\n'
    lines += 'def lasthash():\n    u"git hash"\n    return "%s"\n\n'
    lines += 'def hashdate():\n    u"git hash date"\n    return "%s"\n\n'
    lines += 'def isdirty ():\n    u"git hash"\n    return %s\n\n'
    lines += 'def compiler():\n    u"compiler used"\n    return "%s"'
    lines %= (git.version(), git.lasthash(),
              git.lastdate(), str(git.isdirty()), bld.cpp_compiler_name())

    with open(bld.bldnode.make_node('version.py').abspath(), 'w') as stream:
        print(lines, file = stream)

    mods = _getmodules(bld)
    builder.build(bld)
    builder.findpyext(bld, set(mod for mod in mods if mod != 'tests'))
    bld.recurse(mods)

@_command
def test(bld):
    u"runs pytests"
    mods  = ('/'+i.split('/')[-1] for i in _getmodules(bld))
    names = (path for path in bld.path.ant_glob(('tests/*test.py', 'tests/*/*test.py')))
    names = (str(name) for name in names if any(i in str(name) for i in mods))
    builder.runtest(bld, *(name[name.rfind('tests'):] for name in names))

def environment(cnf):
    u"prints the environment variables for current configuration"
    print(cnf.env)

@_command
def condaenv(cnf):
    u"prints the conda yaml recipe"
    builder.condaenv('trackanalysis')

@_command
def requirements(cnf):
    u"prints requirements"
    builder.requirements.tostream()

@_command
def condasetup(cnf):
    u"prints requirements"
    builder.condasetup(cnf)
