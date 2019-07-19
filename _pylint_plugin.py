#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"add specifics to pylint"
from   pathlib import Path
import re
import astroid
from astroid import MANAGER
def register(*_):
    "nothing to do"

_MATCH = re.compile(r'^    (?P<name>\w+)\s*=\s*\(')
def _transform_tasks_read_tasks(names):
    string = ""
    with open(
            Path(__file__).parent/"src"/"taskmodel"/"__scripting__"/"tasks.py",
            "r",
            encoding = 'utf-8'
    ) as stream:
        for i in stream:
            if i.startswith("class _DOCHelper"):
                break
        for i in stream:
            match  = _MATCH.match(i)
            if match and match.group('name') not in names:
                name = match.group("name")
                string += f"    {name} = '{name}'\n"
                names.add(name)

            elif i.startswith("class"):
                break
    return string

def _transform_tasks_read_app(names):
    string = ""
    with open(
            Path(__file__).parent/"src"/"taskapp"/"__scripting__.py",
            "r",
            encoding = 'utf-8'
    ) as stream:
        found = False
        cont  = False
        for i in stream:
            if cont:
                string += '    '+i
                cont    = '):' not in i and '->' not in i
                if not cont:
                    string += "        'doc'\n"
            elif i.startswith("@addto(Tasks"):
                found = True
                cont  = False
            elif found:
                found = False
                name  = i[len('def '):].split('(')[0]
                if name in names:
                    continue
                cont = '):' not in i and '->' not in i
                names.add(name)

                if 'pylint' in i:
                    string += f"    {i[:-1]},unused-arguments\n"
                else:
                    string += f"    {i[:-1]} # pylint: disable=unused-arguments\n"
                if not cont:
                    string += "        'doc'\n"
    return string

def _transform_tasks(cls):
    """
    Tasks has a number of attributes added dynamically, the following helps
    pylint find them.
    """

    # In order to help pylint, we parse the files where Tasks is constructed and
    # recreate a fake file better suited to pylint. We then ask pylint to parse it
    # and we add the locals thus created to pylint's Tasks representation
    names   = set(cls.locals)
    string  = """class Tasks(Enum):\n"""
    string += _transform_tasks_read_tasks(names)
    string += _transform_tasks_read_app(names)

    cls.locals.update(list(astroid.parse(string).get_children())[0].locals.items())

_REC = [False]
def transform(cls):
    "add Tasks's dynamic attrs"
    if cls.name == 'Tasks' and not _REC[0]:
        _REC[0] = True
        _transform_tasks(cls)

    if len(cls.bases) == 0 or not isinstance(cls.bases[0], astroid.Subscript):
        return

    name = str(cls.bases[0].value)
    if any(i in name for i in ('PlotView', 'PlotCreator', 'BatchProcessor')):
        # We found a class using Generic, we replace the Subscript and add the
        # base class to pylint's bases
        cls.bases = [cls.bases[0].value]+ cls.bases[1:]

MANAGER.register_transform(astroid.ClassDef, transform)
