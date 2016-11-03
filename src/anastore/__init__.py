#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"""
Track Analysis inputs and outputs.

This does not include track files io.
"""
import json

from ._fromjson import Runner as _InputRunner
from ._tojson   import Runner as _OutputRunner
from ._patches  import run    as _patch

__VERSION__ = 0
def _dump(info):
    return [{'version': __VERSION__}, _OutputRunner()(info)]

def _load(info):
    patched = _patch(info[1], info[0]['version'], __VERSION__)
    return _InputRunner()(patched)

def dumps(info, **kwa):
    u"Dumps data to json. This includes the version number"
    return json.dumps(_dump(info), **kwa)

def dump(info, stream, **kwa):
    u"Dumps data to json file. This includes the version number"
    return json.dump(_dump(info), stream, **kwa)

def loads(stream, **kwa):
    u"Dumps data to json. This includes the version number"
    return _load(json.loads(stream, **kwa))

def load(stream, **kwa):
    u"Dumps data to json file. This includes the version number"
    return _load(json.load(stream, **kwa))
