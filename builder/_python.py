#!/usr/bin/env python
# encoding: utf-8
u"All *basic* python related details"
import subprocess
import shutil
import re

from typing     import Sequence, List
from contextlib import closing

from ._utils    import YES
from ._utils    import Make, addconfigure, runall, addmissing

from waflib.Context import Context # type: ignore

IS_MAKE = YES

def _store(cnf:Context, flg:str):
    for item in 'PYEXT', 'PYEMBED':
        cnf.parse_flags(flg, uselib_store=item)

@addconfigure
def numpy(cnf:Context):
    u"tests numpy and obtains its headers"
    cnf.check_python_module('numpy',  condition = 'ver >= num(1,11,0)')

    cmd = cnf.env.PYTHON[0]                                     \
        + ' -c "from numpy.distutils import misc_util as n;'    \
        + ' print(\'-I\'.join([\'\']+n.get_numpy_include_dirs()))"'
    flg = subprocess.check_output(cmd, shell=True).decode("utf-8")
    _store(cnf, flg)

class PyBind11(Make):
    u"tests pybind11 and obtains its headers"
    @staticmethod
    def options(opt):
        opt.get_option_group('Python Options')\
           .add_option('--pybind11',
                       dest    = 'pybind11',
                       default = None,
                       action  = 'store',
                       help    = 'pybind11 include path')

    @staticmethod
    def configure(cnf):
        if cnf.options.pybind11 is not None:
            _store(cnf, '-I'+cnf.options.pybind11)

        cnf.env.append_unique('CXXFLAGS_PYEXT', '-std=c++14')
        def _build(bld):
            lib_node = bld.srcnode.make_node('pybind11example.cpp')
            lib_node.write("""
                          #include <pybind11/pybind11.h>

                          int add(int i, int j) { return i + j; }
                          using namespace pybind11;

                          PYBIND11_PLUGIN(example)
                          {
                                module m("example", "pybind11 example");
                                m.def("add", &add, "A function which adds two numbers");
                                return m.ptr();
                          }
                          """, 'w')
            bld.shlib(features='pyext cxxshlib',
                      source=[lib_node],
                      target='pybind11example')

        cnf.check_cxx(build_fun = _build,
                      msg       = 'checking for pybind11',
                      mandatory = True)

def loads():
    u"returns python features to be loaded"
    return 'python'

@runall
def configure(cnf:Context):
    u"get python headers and modules"
    cnf.check_python_version((3,5))
    cnf.check_python_headers()
    cnf.find_program("mypy",   var = "MYPY")
    cnf.find_program("pylint", var = "PYLINT")

def pymoduledependencies(pysrc):
    u"detects dependencies"
    patterns = tuple(re.compile(r'^\s*'+pat) for pat in
                     (r'from\s+(\w+)\s+import\s+', r'import\s*(\w+)'))
    mods     = set()
    for item in pysrc:
        with closing(open(item.abspath(), 'r')) as stream:
            for line in stream:
                for pat in patterns:
                    ans = pat.match(line)
                    if ans is not None:
                        mods.add(ans.group(1))
    return mods

def findpyext(bld:Context, items:Sequence):
    u"returns a list of pyextension in that module"
    names = list(items)
    bld.env.pyextmodules = set()
    for name in names:
        path = bld.path.make_node(str(name))
        if haspyext(path.ant_glob('**/*.cpp')):
            bld.env.pyextmodules.add(name[name.rfind('/')+1:])

def haspyext(csrc):
    u"detects whether pybind11 is used"
    pattern = re.compile(r'\s*#\s*include\s*["<]pybind11')
    for item in csrc:
        with closing(open(item.abspath(), 'r')) as stream:
            if any(pattern.match(line) is not None for line in stream):
                return True
    return False

def checkpy(bld:Context, items:Sequence):
    u"builds tasks for checking code"
    if len(items) == 0:
        return
    deps    = list(pymoduledependencies(items) & bld.env.pyextmodules)
    def _scan(_):
        nodes = [bld.get_tgen_by_name(dep+'pyext').tasks[-1].outputs[0] for dep in deps]
        return (nodes, [])

    plrule  = '${PYLINT} ${SRC} --init-hook="sys.path.append(\'./\')" '
    plrule += '-f text --reports=no'

    rules  = [dict(color       = 'BLUE',
                   rule        = '${MYPY} ${SRC} --silent-imports',
                   scan        = _scan,
                   cls_keyword = lambda _: 'MyPy'),
              dict(color       = 'YELLOW',
                   rule        = plrule,
                   scan        = _scan,
                   cls_keyword = lambda _: 'PyLint'),
             ] # type: List

    for item in items:
        for kwargs in rules:
            tsk = bld(source = [item], **kwargs)

def copypy(bld:Context, arg, items:Sequence):
    u"copy py modules to build root path"
    if len(items) == 0:
        return

    def _cpy(tsk):
        shutil.copy2(tsk.inputs[0].abspath(),
                     tsk.outputs[0].abspath())
    def _kword(_):
        return 'Copying'

    root = bld.bldnode.make_node('/'+arg) if isinstance(arg, str) else arg
    root.mkdir()
    for item in items:
        bld(rule = _cpy, source = item, target = root, cls_keyword = _kword)

def buildpymod(bld:Context, name:str, pysrc:Sequence):
    u"builds a python module"
    if len(pysrc) == 0:
        return
    bld    (features = "py", source = pysrc)
    checkpy(bld, pysrc)
    copypy (bld, name, pysrc)

def buildpyext(bld     : Context,
               name    : str,
               version : str,
               pysrc   : Sequence,
               csrc    : List,
               **kwargs):
    u"builds a python extension"
    if len(csrc) == 0:
        return

    if name not in bld.env.pyextmodules and not haspyext(csrc):
        return

    args    = kwargs
    bldnode = bld.bldnode.make_node(bld.path.relpath())
    haspy   = len(pysrc)
    mod     = '_'+name+'_core'                if haspy else name
    parent  = bld.bldnode.make_node('/'+name) if haspy else bld.bldnode

    node    = bld(features = 'subst',
                  source   = bld.srcnode.find_resource('builder/_module.template'),
                  target   = name+"module.cpp",
                  nsname   = name,
                  module   = mod,
                  version  = version)
    csrc.append(node.target)

    args.setdefault('source',   csrc)
    args.setdefault('target',   parent.path_from(bldnode)+"/"+mod)
    args.setdefault('features', ['pyext'])
    args.setdefault('name',     name+"pyext")
    bld.shlib(**args)

def buildpy(bld:Context, name:str, version:str, **kwargs):
    u"builds a python module"
    csrc   = bld.path.ant_glob('**/*.cpp')
    pysrc  = bld.path.ant_glob('**/*.py')

    buildpymod(bld, name, pysrc)
    buildpyext(bld, name, version, pysrc, csrc, **kwargs)

def makemodule(glob:dict, **kw):
    u"returns a method for creating cpp modules"
    def build(bld:Context):
        u"builds a python module"
        buildpy(bld, glob['APPNAME'], glob['VERSION'], **kw)
    return build

addmissing(locals())
