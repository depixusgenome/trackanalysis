#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Default cpp for waf"
from ._utils import YES, runall, addmissing, Make
from waflib  import Utils

IS_MAKE = YES
CXX_OPTION_GROUP = 'C++ Options'

class Flags(Make):
    u"deal with cxx/ld flags"
    @staticmethod
    def options(opt):
        u"add options"
        copt = opt.get_option_group(CXX_OPTION_GROUP)
        copt.add_option('--cxxflags',
                        dest    = 'cxxflaglist',
                        default = '-std=c++14 -fopenmp -g',
                        action  = 'store',
                        help    = 'define cxx flags')
        copt.add_option('--linkflags',
                        dest    = 'linkflaglist',
                        default = '-fopenmp',
                        action  = 'store',
                        help    = 'define link flags')
        copt.add_option('--no-openmp',
                       dest     = 'noopenmp',
                       default  = False,
                       action   = 'store_true',
                       help     = 'disable OpenMP')
    @staticmethod
    def configure(cnf):
        u"setup configure"
        cxx = cnf.options.cxxflaglist
        ld  = cnf.options.linkflaglist
        if cnf.options.noopenmp:
            cxx = cxx.replace('-fopenmp', '')
            ld  = ld .replace('-fopenmp', '')

        cnf.check(features  = 'cxx cxxprogram',
                  cxxflags  = cxx,
                  linkflags = ld,
                  mandatory = True)

        cnf.env.append_unique('CXXFLAGS',  Utils.to_list(cxx))
        cnf.env.append_unique('LINKFLAGS', Utils.to_list(ld))
        cnf.env.append_unique('INCLUDES',  ['../']);

        warnings = [
            '-Werror=implicit-function-declaration',
            '-W', '-Wall', '-Wextra','-Wno-write-strings', '-Wunused',
            '-Wmaybe-uninitialized', '-fno-common', '-Winit-self', '-Winline', '-Wpacked',
            '-Wpointer-arith', '-Wmissing-format-attribute',
            '-Wmissing-noreturn',
            '-Wswitch-enum', '-Wundef',
            '-Wunreachable-code',
            '-Wmissing-include-dirs',
            '-Wparentheses',
            '-Wsequence-point',
            ]
        cnf.env.append_unique('CXXFLAGS', warnings)

def loads():
    u"returns all features needed by cpp"
    return 'compiler_cxx'

@runall
def options(opt):
    u"add options"
    opt.add_option_group(CXX_OPTION_GROUP)

addmissing(locals())
