#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"""
Track Analysis inputs and outputs.

This does not include track files io.
"""
import json
import os

from ._fromjson import Runner as _InputRunner
from ._tojson   import Runner as _OutputRunner
from ._patches  import Patches
from ._default  import __TASKS__, __CONFIGS__

def _dump(info, addversion = True):
    if addversion:
        return _OutputRunner()(__TASKS__.dumps(info))
    else:
        return _OutputRunner()(info)

def _load(info, addversion = True):
    if addversion:
        return _InputRunner()(__TASKS__.loads(info))
    else:
        return _InputRunner()(info)

def dumps(info, addversion = True, **kwa):
    u"Dumps data to json. This includes the version number"
    return json.dumps(_dump(info, addversion), **kwa)

def dump(info, arg, **kwa):
    u"Dumps data to json file. This includes the version number"
    if isinstance(arg, str):
        with open(arg, 'w') as stream:
            return json.dump(_dump(info), stream, **kwa)
    return json.dump(_dump(info), arg, **kwa)

def loads(stream, **kwa):
    u"Dumps data to json. This includes the version number"
    return _load(json.loads(stream, **kwa))

def load(arg, **kwa):
    u"Dumps data to json file. This includes the version number"
    if isinstance(arg, str):
        if isana(arg):
            with open(arg) as stream:
                return _load(json.load(stream, **kwa))
        return None
    return _load(json.load(arg, **kwa))

def isana(path):
    u"Wether the file as an analysis file"
    if not (os.path.exists(path) and os.path.isfile(path)):
        return False

    try:
        with open(path, 'r') as stream:
            return stream.read(len('[{"version":')) == '[{"version":'
    except: # pylint: disable=bare-except
        return False
