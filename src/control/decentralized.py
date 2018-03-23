#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Decentralized controller"
from  typing        import Dict, Any
from  collections   import ChainMap
from  copy          import deepcopy
from  utils         import initdefaults
from  .event        import Controller

DELETE = type('DELETE', (), {})

def updatemodel(self, model, kwa, force = False, deflt = None):
    "update the model"
    kwa = {i:j for i, j in kwa.items()
           if hasattr(model, i) and getattr(model, i) != j}

    if len(kwa) == 0 and not force:
        return None

    old = {i: getattr(model, i) for i in kwa}
    rem = {i: getattr(model, i) for i,j in kwa.items() if j is DELETE}
    for i, j in kwa.items():
        if j is DELETE:
            j = getattr(model.__class__, i) if deflt is None else getattr(deflt, i)
        setattr(model, i, j)

    return dict(control = self, model = model,  old = old, deleted = rem)

def updatedict(self, model, kwa, force = False):
    "updatemodelate the model"
    if len(kwa) == 0 and not force:
        return None

    new = {i:j         for i, j in kwa.items() if i not in model}
    old = {i: model[i] for i, j in kwa.items() if i in model and model[i] != j}
    rem = {i: model[i] for i, j in kwa.items() if j is DELETE}
    if len(old) + len(new) + len(rem) == 0:
        return None

    model.update(**kwa)
    for i in rem:
        model.pop(i)
    return dict(control = self, model = model,  old = old, new = new, deleted = rem)

class DecentralizedController(Controller):
    """
    Controller to which can be added anything
    """
    DELETE                     = DELETE
    name                       = ''
    _objects:   Dict[str, Any] = {}
    _defaults:  Dict[str, Any] = {}
    @initdefaults(frozenset(locals()), objects  = '_', defaults = '_')
    def __init__(self, **kwa):
        super().__init__(**kwa)

    def add(self, obj):
        "add a model to be updated & observed through this controller"
        assert obj.name not in self._objects
        self._objects[obj.name]  = obj
        self._defaults[obj.name] = deepcopy(obj)

    def keys(self):
        "return the available keys in this controller"
        return self._defaults.keys()

    def values(self, defaults = False):
        "return the available values in this controller"
        return (self._defaults if defaults else self._objects).values()

    def items(self, defaults = False):
        "return the available items in this controller"
        return (self._defaults if defaults else self._objects).items()

    def __contains__(self, val):
        return ((val in self._objects) if isinstance(val, str) else
                any(i is val for i in self._objects.values()))

    def updatedefaults(self, name, **kwa):
        "update a specific display and emits an event"
        dflt   = self._defaults[name]
        isdict = isinstance(dflt, dict)
        if not isdict:
            if any(i is DELETE for i in kwa.values()):
                raise ValueError("No deleting of attributes allowed")

            missing = set(kwa) - set(dflt.__dict__)
            if len(missing):
                raise KeyError(f"Unknown keys {missing}")

        out = self.__update('_defaults', name, kwa)
        if out is None:
            return

        obj = self._objects[name]
        if isdict:
            fcn = lambda x: obj.get(x, DELETE), lambda x: dflt.get(x, DELETE)
        else:
            fcn = (lambda x: getattr(obj, x)), (lambda x: getattr(dflt, x))

        kwa  = {i: fcn[1](i) for i, j in out['old'].items() if j == fcn[0](i)}
        if isdict:
            kwa.update(dict.fromkeys(out.get('deleted', ()), DELETE))
        kwa.update(out.get('new', ()))
        self.__update('_objects', name, kwa)
        return out

    def update(self, name, defaults = False, **kwa):
        "update a specific display and emits an event"
        if defaults:
            return self.updatedefaults(name, **kwa)

        dflt = self._defaults[name]
        dels = set(i for i, j in kwa.items() if j is DELETE)

        if isinstance(dflt, dict):
            missing = set(kwa) - dels - set(self._defaults[name])
            kwa.update({i: dflt[i] for i in dels})
        else:
            missing = set(kwa) - set(self._defaults[name].__dict__)
            kwa.update({i: getattr(dflt, i) for i in dels})

        if len(missing):
            raise KeyError(f"Unknown keys {missing}")

        return self.__update('_objects', name, kwa)

    def model(self, name, defaults = False):
        "return the model associated to a name or `None` if not found"
        name = getattr(name, 'name', name)
        return (self._defaults if defaults else self._objects).get(name, None)

    def observe(self, *anames, decorate = None, argstest = None, **kwargs):
        """
        or, using the model
        ```python

        class Model:
            name = "model"
            ...

        mdl = Model()
        ctrl.add(mdl)
        ctrl.observe(mdl, lambda **_: None)
        """
        objs   = self._objects.values()
        anames = tuple((self.name+i.name) if any(i is j for j in objs) else i
                       for i in anames)
        super().observe(*anames, decorate = decorate, argstest = argstest, **kwargs)

    @property
    def current(self)-> Dict[str, Dict]:
        "return a dict containing all objects info"
        return self.__get(self._objects)

    @property
    def defaults(self)-> Dict[str, Dict[str, Any]]:
        "return a dict containing all objects info"
        return self.__get(self._defaults)

    @property
    def config(self) -> Dict[str, ChainMap]:
        "returns a chainmap with default values & their changes"
        right = self.current
        return {i: ChainMap({j: k for j, k in right[i].items() if k != dflt[j]},
                            dflt)
                for i, dflt in self.defaults.items()}

    @staticmethod
    def __get(dico)-> Dict[str, Dict[str, Any]]:
        "return a dict containing all objects info"
        get = lambda i: i if isinstance(i, dict) else i.__dict__
        return {i: get(j) for i, j in dico.items()}

    def __update(self, key:str, name, kwa: Dict[str, Any]):
        "update a specific display and emits an event"
        name = getattr(name, 'name', name)
        obj  = getattr(self, key)[name]

        out  = (updatedict(self, obj, kwa) if isinstance(obj, dict) else
                updatemodel(self, obj, kwa, False))

        if out is not None:
            self.handle(self.name + name + ('' if key == '_objects' else 'defaults'),
                        self.emitpolicy.outasdict,
                        out)
        return out

    def __undo__(self, wrapper):
        @wrapper
        def _undo_method(control = None, model = None, old = None, **_):
            assert control.model(model, True) is model or control.model(model) is model
            control.update(model, defaults = control.model(model) is model, **old)

        easy = set(i for i, j in self._objects.items() if not hasattr(j, '__undo__'))
        self.observe(*easy, _undo_method)
        for i in set(self._objects) - easy:
            self._objects[i].__undo__(wrapper)
