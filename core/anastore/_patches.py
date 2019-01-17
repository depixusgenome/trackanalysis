#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Patch mechanism

# Modifying classes: function `modifyclasses`
{}

# Modifying keys: function `modifykeys`
{}

"""
from copy    import copy
from typing  import Optional, Callable, List, Sequence, cast
import re

from utils   import initdefaults
from ._utils import TPE, CNT

class DELETE(Exception):
    "Delete classes or attributes"

class RESET(DELETE):
    "Reset classes or attributes"

class Patches:
    "This must contain json patches up to the app's versions number"
    def __init__(self, *patches):
        self._patches: List[Callable] = list(patches)

    def patch(self, fcn: Callable):
        "registers a patch"
        self._patches.append(fcn)

    @property
    def version(self):
        "The current version: this is independant of the git tag"
        return len(self._patches)

    def dumps(self, info):
        "adds the version to json"
        return [{'version': self.version}, info]

    def loads(self, info):
        "updates json to current version"
        vers = info[0]['version']
        data = info[1]

        if vers < self.version:
            for fcn in self._patches[vers:]:
                data = fcn(data)
                assert data is not None

        elif vers > self.version:
            raise IOError("Anastore file version is too high", "warning")
        return data

class LocalPatch:
    """
    define a local patch. NOT THREADSAFE
    """
    modifications    = ("peakcalling.processor.fittoreference.FitToReferenceTask", DELETE,
                        "peakcalling.processor.fittohairpin.FitToHairpinTask",     DELETE)
    path:    Optional[Callable[[Sequence[str]], Sequence[str]]] = None
    patches: Optional[Patches]                                  = None
    _old:    Patches

    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        pass

    def _modify(self, data:dict) -> dict:
        mods = tuple(self.modifications)
        if self.path is not None: # type: ignore
            def _pathpatch(val):
                # pylint: disable=not-callable
                val[CNT] = self.path(cast(Sequence[str], val[CNT])) # type: ignore
                return val
            mods += "model.task.track.TrackReaderTask", dict(path = _pathpatch)
        modifyclasses(data, *mods)
        return data

    def __enter__(self):
        if self.patches is None:
            from ._default import __TASKS__ as patches
        else:
            patches = self.patches

        self._old = copy(patches)
        patches.patch(self._modify)
        return patches

    def __exit__(self, *_):
        if self.patches is None:
            from ._default import __TASKS__ as patches
        else:
            patches = self.patches
        patches.__dict__.update(self._old.__dict__)

class ModyfyClasses:
    """
    Scans the data applying listed patches.

    The arguments should be a flat list of pairs:

    ```python
    modifyclasses(data,
                  "modulename1.classname1", dict(attr1 = lambda val: val*2),
                  "modulename2.classname2", dict(attr2 = lambda val: val/2,
                                                 attr3 = Reset,
                                                 __name__ = 'newmod.newcls'),
                  "modulename2.classname2", dict(attr4 = 'newname'),
                  "modulename3.classname3", DELETE,
                  "*.classname4", dict(__call__ = specific)) # using regex
    ```

    Use `DELETE` to remove a class or attribute. Use `RESET` to reset an
    attribute to it's - possibly new - default value. In practice, using
    `DELETE` has the same effect as `RESET`: the key is removed from the
    dictionnary.

    A same class can have multiple dictionnaries, allowing incremental changes.

    **Note**: If a default value has changed, do not set to the new value.
    Return or raise `RESET`.

    **Note**: If a value should be set to default, do not set it.  Return or
    raise `RESET`.

    It's also possible to update the whole dictionary by adding a *__call__* key.
    In such a case, its value should accept a single argument: the dictionnary.
    """
    def __init__(self, *args):
        assert len(args) % 2 == 0
        self.reps = tuple((re.compile(args[2*i]), args[2*i+1]) for i in range(len(args)//2))

    def _list_scan(self, itm):
        cnt = len(itm)
        for i, val in enumerate(tuple(itm)[::-1]):
            if isinstance(val, (dict, list)):
                try:
                    self.scan(val)
                except DELETE:
                    itm.pop(cnt-i-1)

    def _dict_scan(self, itm):
        cls  = itm.get(TPE, None)
        good = []
        if cls is not None:
            for patt, cur in self.reps:
                if patt.match(cls) is None:
                    continue

                if cur is DELETE:
                    raise DELETE()

                if cur is RESET:
                    itm.clear()
                    itm[TPE] = cls
                    return

                good.append(cur)

        for key, val in tuple(itm.items()):
            if isinstance(val, (dict, list)):
                try:
                    self.scan(val)
                except DELETE:
                    itm.pop(key)

        yield from good

    @staticmethod
    def _modify_name(itm, cur):
        fcn = cur.get('__name__', cur.get(TPE, None))
        if callable(fcn):
            itm[TPE] = fcn(itm[TPE])
        elif isinstance(fcn, str):
            itm[TPE] = fcn
        elif fcn is not None:
            assert False

    @classmethod
    def _attr_update(cls, itm, cur):
        fcn = cur.get('__call__', None)
        if fcn is not None:
            fcn(itm)

        cls._modify_name(itm, cur)

        # pylint: disable=too-many-nested-blocks
        for key in frozenset(itm) & frozenset(cur):
            fcn = cur[key]
            if fcn is DELETE or fcn is RESET:
                itm.pop(key)

            elif isinstance(fcn, str):
                itm[fcn] = itm.pop(key)

            elif callable(fcn):
                try:
                    val = fcn(itm[key])
                except DELETE:
                    itm.pop(key)
                else:
                    if val is DELETE or val is RESET:
                        itm.pop(key)
                    else:
                        itm[key] = val
            else:
                raise NotImplementedError()

    def scan(self, itm):
        "Scan a dict or list and applies changes"
        if isinstance(itm, list):
            self._list_scan(itm)

        elif isinstance(itm, dict):
            for cur in self._dict_scan(itm):
                self._attr_update(itm, cur)

def modifyclasses(data, *args):
    """
    Scans the data applying listed patches.
    """
    ModyfyClasses(*args).scan(data)
if modifyclasses.__doc__:
    modifyclasses.__doc__ = ModyfyClasses.__doc__

def modifykeys(data, *args, **kwa):
    """
    Finds a specific key and modifies its value.

    ```python
    data["key1"] = dict(key2 = 1)
    modifykey(data,  "key1", "key2", lambda val: val*2)
    assert data["key1"]["key2"] = 2

    data = {}
    modifykey(data,  "key1", "key2", lambda val: val*2)
    ```
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

if locals().get('__doc__', None):
    locals()['__doc__'] = locals()['__doc__'].format(modifyclasses.__doc__, modifykeys.__doc__)
