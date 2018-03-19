#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Decentralized controller"
from  typing        import Dict, Any
from  collections   import ChainMap
from  copy          import deepcopy
from  .event        import Controller

def updatemodel(self, model, kwa, force = False):
    "update the model"
    kwa  = {i:j for i, j in kwa.items()
            if hasattr(model, i) and getattr(model, i) != j}

    if len(kwa) == 0 and not force:
        return None

    old  = {i: getattr(model, i) for i in kwa}
    for i, j in kwa.items():
        setattr(model, i, j)
    return dict(control = self, model = model,  old = old)

def updatedict(self, model, kwa, force = False):
    "updatemodelate the model"
    if len(kwa) == 0 and not force:
        return None

    new = {i:j         for i, j in kwa.items() if i not in model}
    old = {i: model[i] for i, j in kwa.items() if i in model and model[i] != j}
    if len(old) == 0 and len(new) == 0:
        return None

    model.update(**kwa)
    return dict(control = self, model = model,  old = old, new = new)

class DecentralizedController(Controller):
    """
    Controller to which can be added anything
    """
    def __init__(self, **kwa):
        super().__init__(**kwa)
        self._objects:   Dict[str, Any] = {}
        self._defaults:  Dict[str, Any] = {}

    def add(self, obj):
        "add a model to be updated & observed through this controller"
        assert obj.NAME not in self._objects
        self._objects[obj.NAME]  = obj
        self._defaults[obj.NAME] = deepcopy(obj)

    def updatedefaults(self, name, **kwa):
        "update a specific display and emits an event"
        out = self.__update('_defaults', name, kwa)
        if out is None:
            return
        obj  = self._objects[name]
        dflt = self._defaults[name]
        if not isinstance(obj, dict):
            fcn = (lambda x: getattr(obj, x)), (lambda x: getattr(dflt, x))
        else:
            fcn = obj.__getitem__, dflt.__getitem__
        kwa  = {i: fcn[1](i) for i, j in out['old'].items() if j == fcn[0](i)}
        kwa.update(out.get('new', {}))
        self.__update('_objects', name, kwa)
        return out

    def update(self, name, **kwa):
        "update a specific display and emits an event"
        if isinstance(self._defaults[name], dict):
            missing = set(kwa) - set(self._defaults[name])
            if len(missing):
                raise KeyError(f"Unknown keys {missing}")
        return self.__update('_objects', name, kwa)

    def model(self, name):
        "return the model associated to a name"
        return self._objects[name]

    @property
    def current(self)-> Dict[str, Dict]:
        "return a dict containing all objects info"
        return self.__get(self._objects)

    @property
    def defaults(self)-> Dict[str, Dict[str, Any]]:
        "return a dict containing all objects info"
        return self.__get(self._defaults)

    @property
    def chainmap(self) -> ChainMap:
        "returns a chainmap with default values & their changes"
        left  = self.defaults
        right = self.current
        ret   = {}
        for i, dflt in left.items():
            cur = right[i]
            cha = {j: k for j, k in cur.items() if k != dflt[j]}
            if len(cha):
                ret[i] = cha

        return ChainMap(ret, left)

    @staticmethod
    def __get(dico)-> Dict[str, Dict[str, Any]]:
        "return a dict containing all objects info"
        get = lambda i: i if isinstance(i, dict) else i.__dict__
        return {i: get(j) for i, j in dico.items()}

    def __update(self, key:str, name, kwa: Dict[str, Any]):
        "update a specific display and emits an event"
        name = getattr(name, 'NAME', name)
        obj  = getattr(self, key)[name]
        out  = (updatedict(self, obj, kwa) if isinstance(obj, dict) else
                updatemodel(self, obj, kwa))

        if out is not None:
            self.handle(name if key == '_objects' else 'defaults'+name,
                        self.emitpolicy.outasdict,
                        out)
        return out
