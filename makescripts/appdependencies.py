#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Finds module dependencies"
import sys
from typing     import List
from pathlib    import Path

sys.path.append(str(Path(".").resolve()))

_TA_PATH = Path(__file__).resolve().parent.parent/"build"
def finddependencies(*modules) -> List[str]:
    "compiles the application as would a normal call to bokeh"
    path = str(_TA_PATH)
    for mod in modules:
        __import__(mod)
    mods = frozenset(i.split('.')[0] for i, j in sys.modules.items()
                     if getattr(j, '__file__', '').startswith(path))
    return sorted(mods)

if __name__ == '__main__':
    # pylint: disable=no-value-for-parameter
    import click
    @click.command()
    @click.argument('modules', nargs = -1)
    @click.option("-o", "--output", type = click.Path(), default = None)
    def _main(modules, output):
        string = '\n'.join(finddependencies(*modules))
        if output is None:
            print(string)
        else:
            print(string, file = open(output, 'w'))
    _main()
