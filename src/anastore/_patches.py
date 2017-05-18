#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"""
Patch mechanism
"""
from typing  import Callable, List # pylint: disable=unused-import
from ._utils import TPE

class Patches:
    u"This must contain json patches up to the app's versions number"
    def __init__(self, *patches):
        self._patches = list(patches) # type: List[Callable]

    def patch(self, fcn: Callable):
        u"registers a patch"
        self._patches.append(fcn)

    @property
    def version(self):
        u"The current version: this is independant of the git tag"
        return len(self._patches)

    def dumps(self, info):
        u"adds the version to json"
        return [{'version': self.version}, info]

    def loads(self, info):
        u"updates json to current version"
        vers = info[0]['version']
        data = info[1]

        if vers < self.version:
            for fcn in self._patches[vers:]:
                data = fcn(data)
                assert data is not None

        elif vers > self.version:
            raise IOError("Anastore file version is too high", "warning")
        return data

def modifyclasses(data, *args):
    """
    Scans the data applying listed patches.

    The arguments should be a flat list of pairs:

        >>> modifyclasses(data,
        ...               "modulename1.classname1", dict(attr1 = lambda val: val*2),
        ...               "modulename2.classname2", dict(attr2 = lambda val: val/2))

    """
    assert len(args) % 2 == 0
    reps  = {args[2*i]: args[2*i+1] for i in range(len(args)//2)}
    empty = {}
    def _scan(itm):
        if isinstance(itm, list):
            for val in itm:
                if isinstance(val, (dict, list)):
                    _scan(val)

        elif isinstance(itm, dict):
            for val in itm.values():
                if isinstance(val, (dict, list)):
                    _scan(val)

            cur = reps.get(itm.get(TPE, None), empty)
            itm.update((key, cur[key](itm[key])) for key in set(itm) & set(cur))

    _scan(data)

def modifykeys(data, *args, **kwa):
    """
    Finds a specific key and modifies its value.

        >>> data["key1"] = dict(key2 = 1)
        >>> modifykey(data,  "key1", "key2", lambda val: val*2)
        >>> assert data["key1"]["key2"] = 2

        >>> data = {}
        >>> modifykey(data,  "key1", "key2", lambda val: val*2)

    """
    for key in args[:None if len(kwa) else -2]:
        if ((isinstance(data, dict) and key in data)
                or isinstance(data, list) and len(data) > key):
            data = data[key]
        else:
            return

    if len(kwa):
        data[args[-2]] =  args[-1](data[args[-2]])
    else:
        for key, val in kwa.items():
            data[key] =  val(data[key])
