#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"""
Track Analysis inputs and outputs.

This does not include track files io.
"""
from   typing   import Union, IO, Any
from   pathlib  import Path
import json
import os

from ._fromjson import Runner as _InputRunner
from ._tojson   import Runner as _OutputRunner
from ._patches  import Patches
from ._default  import __TASKS__, __CONFIGS__

def _apply(info, patch, patchfcn, inout):
    if patch == 'tasks':
        patch = __TASKS__
    elif patch == 'config':
        patch = __CONFIGS__
    else:
        return inout()(info)

    return inout()(getattr(patch, patchfcn)(info))

def dumps(info:Any, patch = 'tasks', **kwa):
    u"Dumps data to json. This includes the version number"
    return json.dumps(_apply(info, patch, 'dumps', _OutputRunner), **kwa)

def dump(info:Any, path:Union[str,Path,IO], patch = 'tasks', **kwa):
    u"Dumps data to json file. This includes the version number"
    if isinstance(path, (Path, str)):
        with open(str(Path(path).absolute()), 'w', encoding = 'utf-8') as stream:
            return dump(info, stream, **kwa)
    return json.dump(_apply(info, patch, 'dumps', _OutputRunner), path, **kwa)

def loads(stream:str, patch = 'tasks', **kwa):
    u"Dumps data to json. This includes the version number"
    return _apply(json.loads(stream, **kwa), patch, 'loads', _InputRunner)

def load(path:Union[str,Path,IO], patch = 'tasks', **kwa):
    u"Dumps data to json file. This includes the version number"
    if isinstance(path, (Path, str)):
        if isana(path):
            with open(str(Path(path).absolute()), 'r', encoding = 'utf-8') as stream:
                return load(stream, patch, **kwa)
        return None

    return _apply(json.load(path, **kwa), patch, 'loads', _InputRunner)

def isana(path: Union[str, Path]):
    u"Wether the file as an analysis file"
    path = Path(path)
    if not path.is_file():
        return False

    const = '[{"version":'
    try:
        with open(str(path), 'r', encoding = 'utf-8') as stream:
            line = stream.read(100).replace('\n', '').replace(' ', '')
            return line[:len(const)] == const
    except: # pylint: disable=bare-except
        return False

def version(patch):
    u"returns the current version"
    if patch == 'tasks':
        patch = __TASKS__
    elif patch == 'config':
        patch = __CONFIGS__
    else:
        return None
    return 'v%d' % patch.version

def iterversions(patch):
    u"iters over possible versions"
    if patch == 'tasks':
        patch = __TASKS__
    elif patch == 'config':
        patch = __CONFIGS__
    else:
        yield None
        return

    for i in range(patch.version, -1, -1):
        yield 'v%d' % i
