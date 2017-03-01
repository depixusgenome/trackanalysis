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
from ._patches  import run    as _patch

__VERSION__ = 0
def _dump(info, addversion = True):
    if addversion:
        return [{'version': __VERSION__}, _OutputRunner()(info)]
    return _OutputRunner()(info)

def _load(info):
    patched = _patch(info[1], info[0]['version'], __VERSION__)
    return _InputRunner()(patched)

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
