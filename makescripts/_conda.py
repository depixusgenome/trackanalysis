#!/usr/bin/env python3
# encoding: utf-8
"Everything related to conda"
import sys
from pathlib    import Path
from itertools  import chain
from zipfile    import ZipFile
from shutil     import rmtree
import py_compile

from waflib             import Logs

import wafbuilder
from   ._utils          import BaseContext, BuildContext, MODULES
from   ._base           import build as _basebuild

class _CondaEnv(BuildContext):
    fun = cmd = 'condaenv'
def condaenv(cnf):
    u"prints the conda yaml recipe"
    MODULES(cnf)
    wafbuilder.condaenv('trackanalysis')

class _CondaSetup(BaseContext):
    fun = cmd = 'setup'

def setup(cnf):
    "Sets up the python environment"
    MODULES(cnf)
    wafbuilder.condasetup(cnf)
    print('********************************************')
    print('********************************************')
    print("BOOST must be installed manually")
    if sys.platform.startswith("win"):
        print("COFFEESCRIPT is not mandatory & can be installed manually")
    print('********************************************')
    print('********************************************')

class _CondaApp(BuildContext):
    fun = cmd = 'app'

    def __clean(self):
        self.options.APP_PATH = self.bldnode.make_node("OUTPUT_PY")
        if self.options.APP_PATH.exists():
            self.options.APP_PATH.delete()

        self.options.STARTSCRIPT_PATH = self.bldnode.make_node("OUTPUT")
        if self.options.STARTSCRIPT_PATH.exists():
            self.options.STARTSCRIPT_PATH.delete()
        self.options.STARTSCRIPT_PATH.mkdir()

    def make_startup_script(self, name, val):
        "creates the startup script"
        iswin = sys.platform.startswith("win")
        ext   = ".bat"                         if iswin else ".sh"
        cmd   = r"start /min %~dp0pythonw -I " if iswin else "./"
        for optext, opts in (('', ''), ('_chrome', ' --electron')):
            fname = str(self.options.STARTSCRIPT_PATH.make_node(name+optext+ext))
            with open(fname, 'w', encoding = 'utf-8') as stream:
                print(cmd + r"app/cmdline.pyc " + val + opts + ' --port random',
                      file = stream)

    def __startscripts(self, mods):
        self.recurse(mods, "startscripts", mandatory = False)

    @staticmethod
    def __electron():
        old   = Path(".").resolve()
        wafbuilder.os.chdir(str(Path("build")/"OUTPUT"))

        iswin = sys.platform.startswith("win")
        npm   = 'npm' + ('.cmd' if iswin else '')
        for path in ('.', 'bin', 'Scripts'):
            if (Path(path)/npm).exists():
                cmd = str(Path(path)/npm) + " install electron"
                Logs.info(cmd)
                wafbuilder.os.system(cmd)
                break
        else:
            raise IOError("Could not install electron")
        wafbuilder.os.chdir(str(old))

    @staticmethod
    def __final(mods):
        path  = Path("build")/"OUTPUT_PY"
        iswin = sys.platform.startswith("win")
        dll   = '.cp*-win*.pyd' if iswin else '.cpython-*.so'


        mods = [path/Path(mod).name for mod in mods]
        zips = [mod for mod in mods
                if (mod.exists() and mod.name != 'app'
                    and next(mod.glob("_core"+dll), None) is None
                    and next(mod.glob("**/*.coffee"), None) is None)]

        def _compile(inp, outp):
            with open(str(inp), encoding = 'utf-8') as stream:
                if not any('from_py_func' in i for i in stream):
                    cur = outp/inp.relative_to(path).with_suffix('.pyc')
                    out = str(cur)
                    opt = 0 if 'reporting' in out else 2
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

        final = Path(".")/wafbuilder.git.version()
        if final.exists():
            rmtree(str(final))
        wafbuilder.os.rename(str(out), str(final))
        rmtree(str(path))

    def build_app(self):
        "builds the app"
        self.__clean()
        mods = [i for i in MODULES(self)
                if not any(j in i for j in ('tests','scripting'))]
        _basebuild(self, mods)
        wafbuilder.condasetup(self, copy = 'build/OUTPUT', runtimeonly = True)
        self.__startscripts(mods)
        self.__electron()

        self.add_group()
        self(rule = lambda _: self.__final(mods), always = True)

def app(bld):
    "Creates an application"
    bld.build_app()

__all__ = ['app', 'setup', 'condaenv']