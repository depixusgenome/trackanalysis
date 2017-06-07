#!/usr/bin/env python3
# encoding: utf-8
from pathlib    import Path
from itertools  import chain
from zipfile    import ZipFile
from shutil     import rmtree
import py_compile
try:
    import wafbuilder as builder
except ImportError:
    raise ImportError("Don't forget to clone wafbuilder!!")
import wafbuilder.git as git
from waflib.Build       import BuildContext, Context
from waflib.Configure   import ConfigurationContext
from waflib             import Logs

require(cxx    = {'msvc'     : 14.0,
                  'clang++'  : 3.8,
                  'g++'      : 5.4},
        rtime = False)

require(python = {'python': 3.5, 'numpy': '1.11.2', 'pandas': '0.19.0'},
        rtime  = True)

require(python = {'pybind11' : '2.1.0',
                  'pylint'   : '1.7.1',
                  'astroid'  : '1.4.8',
                  'mypy'     : '0.511'},
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

    def __clean(self):
        out = git.version()

        self.options.APP_PATH = self.bldnode.make_node("OUTPUT_PY")
        if self.options.APP_PATH.exists():
            self.options.APP_PATH.delete()

        self.options.STARTSCRIPT_PATH = self.bldnode.make_node("OUTPUT")
        if self.options.STARTSCRIPT_PATH.exists():
            self.options.STARTSCRIPT_PATH.delete()
        self.options.STARTSCRIPT_PATH.mkdir()

    def __startscripts(self, mods):
        iswin = builder.os.sys.platform.startswith("win")
        ext   = ".bat"                      if iswin else ".sh"
        cmd   = r"start /min %~dp0pythonw -I " if iswin else "./"
        def make_startup_script(name, val):
            "creates the startup script"
            for optext, opts in (('', ''), ('_chrome', ' --electron')):
               with open(str(self.options.STARTSCRIPT_PATH.make_node(name+optext+ext)), 'w',
                          encoding = 'utf-8') as stream:
                    print(cmd + r"app/cmdline.pyc " + val + opts + ' --port random',
                          file = stream)

        self.make_startup_script = make_startup_script
        self.recurse(mods, "startscripts", mandatory = False)

    def __electron(self):
        old   = Path(".").resolve()
        builder.os.chdir(str(Path("build")/"OUTPUT"))

        iswin = builder.os.sys.platform.startswith("win")
        npm   = 'npm' + ('.cmd' if iswin else '')
        for path in ('.', 'bin', 'Scripts'):
            if (Path(path)/npm).exists():
                cmd = str(Path(path)/npm) + " install electron"
                Logs.info(cmd)
                builder.os.system(cmd)
                break
        else:
            raise IOError("Could not install electron")
        builder.os.chdir(str(old))

    def __final(self, mods):
        path  = Path("build")/"OUTPUT_PY"
        iswin = builder.os.sys.platform.startswith("win")
        dll   = '.cp*-win*.pyd' if iswin else '.cpython-*.so'


        mods = [path/Path(mod).name for mod in mods]
        zips = [mod for mod in mods
                if (mod.exists() and 'app' != mod.name
                    and next(mod.glob("_core"+dll), None) is None
                    and next(mod.glob("**/*.coffee"), None) is None)]

        def _compile(inp, outp):
            with open(str(inp), encoding = 'utf-8') as stream:
                if not any('from_py_func' in i for i in stream):
                    cur = outp/inp.relative_to(path).with_suffix('.pyc')
                    out = str(cur)
                    opt = optimize = 0 if 'reporting' in out else 2
                    py_compile.compile(str(inp), out, optimize = opt)
                    return cur
            return inp

        out = Path("build")/"OUTPUT"
        if len(zips):
            with ZipFile(str(out/"trackanalysis.pyz"), "w") as zfile:
                for pyc in path.glob("*.py"):
                    pyc = _compile(pyc, path)
                    zfile.write(str(pyc), str(pyc.relative_to(path)))

                for mod in zips:
                    for pyc in chain(mod.glob("**/*.pyc"), mod.glob("**/*.py")):
                        pyc = _compile(pyc, path)
                        zfile.write(str(pyc), str(pyc.relative_to(path)))


        for mod in mods:
            if mod in zips:
                continue

            for name in chain(mod.glob('**/*.coffee'), mod.glob("_core"+dll)):
                outp = out/name.relative_to(path)
                outp.parent.mkdir(exist_ok = True, parents = True)
                name.rename(outp)

            for pyc in mod.glob('**/*.py'):
                outp = _compile(pyc, out)
                if outp == pyc:
                    pyc.rename(out/pyc.relative_to(path))

        for name in path.glob('*'+dll):
            outp = out/name.relative_to(path)
            outp.parent.mkdir(exist_ok = True, parents = True)
            name.rename(outp)

        if (path/'static').exists():
            (path/'static').rename(out/'static')

        final = Path(".")/git.version()
        if final.exists():
            rmtree(str(final))
        builder.os.rename(str(out), str(final))
        rmtree(str(path))

    def build_app(self):
        self.__clean()

        mods = [i for i in _getmodules(self) if not any(j in i for j in ('tests','scripting'))]
        build(self, mods)
        builder.condasetup(self, copy = 'build/OUTPUT', runtimeonly = True)
        self.__startscripts(mods)
        self.__electron()

        self.add_group()
        self(rule = lambda _: self.__final(mods), always = True)

def app(bld):
    bld.build_app()
