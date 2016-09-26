#!/usr/bin/env python
# encoding: utf-8

u"All *basic* python related details"
import os
import subprocess
from ._utils import YES
from ._utils import Make, addconfigure, runall, addmissing

from waflib.Context import Context

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

def makemodule(glob:dict, **kw):
    u"returns a method for creating cpp modules"
    def build(bld:Context):
        u"builds a library"
        args  = dict(kw)
        name  = glob['APPNAME']
        csrc  = bld.path.ant_glob('**/*.cpp')
        pysrc = bld.path.ant_glob('**/*.py')
        haspy = len(pysrc)
        mod   = '_'+name+'_core' if haspy else name

        node  = bld(features = 'subst',
                    source   = '../../builder/_module.template',
                    target   = './src/{n}/module.cpp'.format(n = name),
                    name     = name,
                    module   = mod,
                    version  = glob['VERSION'])
        csrc.append(node.target)

        args.setdefault('source', csrc)
        args.setdefault('target', "../../"+(name+'/' if haspy else '')+mod)
        args.setdefault('features', ['pyext'])
        bld.shlib(**args)

        bld(features = ['py'], source = pysrc)
        for src in pysrc:
            node  = bld(features = 'subst',
                        source   = str(src),
                        target   = str(src).replace('src/', ''))

    return build

addmissing(locals())
