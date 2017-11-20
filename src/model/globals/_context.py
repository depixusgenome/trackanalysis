#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Storing global properties"
from typing      import Dict, Any, Tuple, List # pylint: disable=unused-import
from ._access    import BaseGlobalsAccess

ARG_T = Dict[str,Dict[str,Any]]
class LocalContext:
    """
    Isolates the configuration for a period of time.

    It is **NOT THREAD SAFE**.
    """
    def __init__(self, parent, update: ARG_T = None, **kwa) -> None:
        self.__save:    ARG_T = {}
        self.__replace: ARG_T = kwa
        self.__update:  ARG_T = {} if update is None else dict(update)
        self.__parent         = getattr(parent, 'getGlobal', lambda _: parent)(...)

    def __maps(self):
        if callable(getattr(self.__parent, 'items', None)):
            return self.__parent.items()
        for i, j in self.__parent.__dict__.items():
            if i[0] == '_' and i[1].lower() != i[1] and i.endswith("__model"):
                return j.items()
        raise ValueError("could not find maps")

    @staticmethod
    def __apply(first, second, args, kwa):
        "sets replacements"
        new = dict(*args, **kwa)
        cur = set(second) & set(new)
        if cur:
            raise KeyError("Following keys are already set: "+str(cur))
        first.update(new)

    def replace(self, *args, **kwa) -> 'LocalContext':
        "adds replacements to the current context"
        self.__apply(self.__replace, self.__update, args, kwa)
        return self

    def update(self, *args, **kwa) -> 'LocalContext':
        "adds updates to the current context"
        self.__apply(self.__update, self.__replace, args, kwa)
        return self

    def __enter__(self):
        self.__save = {i: j.maps[0] for i, j in self.__maps()}
        reps        = [] # type: List[Tuple[list, Dict[str, Any]]]
        for i, j in self.__maps():
            rep = self.__replace.get(i, None)
            if rep is None:
                rep = dict(j.maps[0])
            rep.update(self.__update.get(i, {}))
            missing = set(rep) - set(j.maps[1])
            if missing:
                raise KeyError("Following keys have no defaults: "+str(missing))
            reps.append((j.maps, rep))

        for i, j in reps:
            i[0] = j
        return self

    def __exit__(self, tpe, val, bkt):
        for i, j in self.__maps():
            j.maps[0] = self.__save[i]

    def __getitem__(self, val):
        return self.__parent.getGlobal(val)

    getGlobal = __getitem__

    config  = property(lambda self: BaseGlobalsAccess(self.__parent, None, 'config'))
    css     = property(lambda self: BaseGlobalsAccess(self.__parent, None, 'css'))
    project = property(lambda self: BaseGlobalsAccess(self.__parent, None, 'project'))
