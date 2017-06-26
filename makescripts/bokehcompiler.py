#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Compiles the JS code once and for all"
import sys
from typing     import List
from functools  import wraps
from pathlib    import Path
import re

import bokeh.util.compiler as _compiler

sys.path.append(str(Path(".").resolve()))
def finddependencies(*modules) -> List[str]:
    "compiles the application as would a normal call to bokeh"
    for mod in modules:
        __import__(mod)
    old = _compiler.nodejs_compile
    lst = []
    def _deps(_1, lang="javascript", file=None): # pylint: disable=unused-argument
        lst.append(file)
        return _compiler.AttrDict({'code': '', 'deps': []})
    _compiler.nodejs_compile = _deps
    _compiler.bundle_all_models()
    _compiler.nodejs_compile = old
    return lst

def compileapp(*modules) -> str:
    "compiles the application as would a normal call to bokeh"
    for mod in modules:
        __import__(mod)
    __import__('app.launcher')
    string = _compiler.bundle_all_models()
    string = re.sub(r'\s\s+', ' ',  string)
    string = re.sub(r'\s*([,;={}()])\s*', lambda x: x.group(1), string)
    return string

def monkeypatch(output):
    "monkeypatches the compiler"
    if Path(output).exists():
        @wraps(_compiler.bundle_all_models)
        def _bundle():
            return ''.join(open(output))
        _compiler.bundle_all_models = _bundle

if __name__ == '__main__':
    # pylint: disable=no-value-for-parameter
    import click
    @click.command()
    @click.argument('modules', nargs = -1)
    @click.option("-o", "--output", type = click.Path(), default = None)
    @click.option("-d", "--dependencies", flag_value = True, default = False)
    def _main(modules, output, dependencies):
        if dependencies:
            string = '\n'.join(finddependencies(*modules))
        else:
            string = compileapp(*modules)

        if output is None:
            print(string)
        else:
            print(string, file = open(output, 'w'))

    _main()
