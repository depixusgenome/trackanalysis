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
    items            = _OutputRunner()(info)
    items['version'] = __VERSION__
    return items

def _load(info):
    _patch(info, info.pop('version')+1, __VERSION__)
    return _InputRunner()(info)

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
