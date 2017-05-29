#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"""
Patch mechanism
"""
from typing  import Callable, List # pylint: disable=unused-import
import re
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

class _Delete(Exception):
    "Used for deleting classes or attributes"
    pass

DELETE = _Delete

class _Reset(_Delete):
    "Used for resetting classes or attributes"
    pass

RESET = _Reset

def modifyclasses(data, *args):
    """
    Scans the data applying listed patches.

    The arguments should be a flat list of pairs:

        >>> modifyclasses(data,
        ...               "modulename1.classname1", dict(attr1 = lambda val: val*2),
        ...               "modulename2.classname2", dict(attr2 = lambda val: val/2,
        ...                                              attr3 = Reset,
        ...                                              __name__ = 'newmod.newcls'),
        ...               "modulename3.classname3", _Delete,
        ...               "modulename4.classname4", dict(__call__ = specific))


    Use *DELETE* to remove a class or attribute. Use *RESET* to reset an
    attribute to it's - possibly new - default value. In practice, using
    *DELETE* has the same effect as *Reset*: the key is removed from the
    dictionnary.

    **Note**: If a default value has changed, do not set to the new value.
    Return or raise *RESET*.

    **Note**: If a value should be set to default, do not set it.  Return or
    raise *RESET*.

    It's also possible to update the whole dictionary by adding a *__call__* key.
    In such a case, its value should accept a single argument: the dictionnary.
    """
    assert len(args) % 2 == 0
    reps  = tuple((re.compile(args[2*i]), args[2*i+1]) for i in range(len(args)//2))
    def _list_scan(itm):
        cnt = len(itm)
        for i, val in enumerate(tuple(itm)[::-1]):
            if isinstance(val, (dict, list)):
                try:
                    _scan(val)
                except _Delete:
                    itm.pop(cnt-i-1)

    def _dict_scan(itm):
        cls  = itm.get(TPE, None)
        good = []
        if cls is not None:
            for patt, cur in reps:
                if patt.match(cls) is None:
                    continue

                if cur is _Delete:
                    raise _Delete()

                if cur is _Reset:
                    itm.clear()
                    itm[TPE] = cls
                    return

                good.append(cur)

        for key, val in tuple(itm.items()):
            if isinstance(val, (dict, list)):
                try:
                    _scan(val)
                except _Delete:
                    itm.pop(key)

        yield from good

    def _attr_update(itm, cur):
        fcn = cur.get('__call__', None)
        if fcn is not None:
            fcn(itm)

        fcn = cur.get('__name__', cur.get(TPE, None))
        if fcn is not None:
            assert isinstance(fcn, str)
            itm[TPE] = fcn

        for key in frozenset(itm) & frozenset(cur):
            fcn = cur[key]
            if fcn is _Delete or fcn is _Reset:
                itm.pop(key)
            elif callable(fcn):
                try:
                    val = fcn(itm[key])
                except _Delete:
                    itm.pop(key)
                else:
                    if val is _Delete or val is _Reset:
                        itm.pop(key)
                    else:
                        itm[key] = val
            else:
                raise NotImplementedError()

    def _scan(itm):
        if isinstance(itm, list):
            _list_scan(itm)

        elif isinstance(itm, dict):
            for cur in _dict_scan(itm):
                _attr_update(itm, cur)

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
