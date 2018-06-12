#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Decentralized controller"
import pickle
from  typing            import Dict, Any
from  collections       import ChainMap
from  contextlib        import contextmanager
from  copy              import deepcopy, copy
import numpy            as     np
from  utils             import initdefaults
from  utils.logconfig   import getLogger
from  .event            import Controller
LOGS   = getLogger(__name__)
DELETE = type('DELETE', (), {})

def _isdiff(left, right):
    if left == right:
        return False
    if isinstance(left, dict):
        if set(left) != set(right):
            return True
        return any(_isdiff(right[i], j) for i, j in left.items())
    if hasattr(left, '__dict__') and left.__dict__ == right.__dict__:
        return False
    return pickle.dumps(left) != pickle.dumps(right)

def _good(model, i, j):
    if not hasattr(model, i):
        return False
    obj = getattr(model, i)
    if isinstance(j, np.ndarray) or isinstance(obj, np.ndarray):
        return True
    try:
        return getattr(model, i) != j
    except ValueError:
        return True # numpy error

def updatemodel(self, model, kwa, force = False, deflt = None):
    "update the model"
    kwa = {i:j for i, j in kwa.items() if _good(model, i, j)}

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

    @staticmethod
    def _objname(obj):
        if isinstance(obj, str):
            return obj

        name = getattr(obj, 'name', None)
        return name if name else type(obj).__name__

    def add(self, obj, noerase = True):
        "add a model to be updated & observed through this controller"
        name = self._objname(obj)
        if name in self._objects:
            if noerase and self.model(name) is not obj:
                raise KeyError(f"key already registered: {name}")
            cur = self.model(name)
            if not isinstance(cur, type(obj)):
                raise TypeError(f"key already registered to a different type: {name}")
            return cur
        else:
            assert name, (name, obj)

        self._objects[name]  = obj
        self._defaults[name] = deepcopy(obj)
        self.handle("added"+name, self.emitpolicy.outasdict,
                    dict(control = self, model = obj))
        return obj

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

    def __getitem__(self, val):
        return self.model(val)

    @contextmanager
    def localcontext(self, **kwa):
        "allows changing the context locally. This is **not** thread safe."
        defaults = {i: copy(j) for i, j in self.defaults.items()}
        current  = {i: copy(j) for i, j in self.current.items()}
        try:
            for i, j in kwa.items():
                self.update(i, **j)

            yield self
        finally:
            for i, j in defaults.items():
                j.pop('name', None)
                self.updatedefaults(i, **j)
            for i, j in current.items():
                j.pop('name', None)
                self.update(i, **j)

    def get(self, val, attr, defaultvalue = '--raise--', defaultmodel = False):
        "gets an attribute from a model"
        mdl = self.model(val, defaultmodel)
        get = ((lambda x: getattr(mdl, x))  if defaultvalue == '--raise--' else
               (lambda x: getattr(mdl, x, defaultvalue)))
        return (get(attr)                         if isinstance(attr, str) else
                {i: get(i) for i in attr.items()} if isinstance(attr, dict) else
                {i: get(i) for i in attr})

    def updatedefaults(self, name, **kwa):
        "update a specific display and emits an event"
        name   = self._objname(name)
        dflt   = self._defaults[name]
        isdict = isinstance(dflt, dict)
        if not isdict:
            if any(i is DELETE for i in kwa.values()):
                exc  = ValueError("No deleting of attributes allowed")
                LOGS.debug(str(exc), stack_info = True)
                raise exc

            missing = set(kwa) - set(dflt.__dict__)
            if len(missing):
                exck  = KeyError(f"Unknown keys {missing}")
                LOGS.debug(str(exck), stack_info = True)
                raise exck

        out = self.__update('_defaults', name, kwa)
        if out is None:
            return None

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
        name = self._objname(name)
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
            exc  = KeyError(f"Unknown keys in {name}: {missing}")
            LOGS.debug(str(exc), stack_info = True)
            raise exc

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
        anames = tuple((self.name+self._objname(i)) if any(i is j for j in objs) else i
                       for i in anames)
        return super().observe(*anames, decorate = decorate, argstest = argstest, **kwargs)

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
        return {i: ChainMap({j: k for j, k in right[i].items() if _isdiff(k, dflt[j])}, dflt)
                for i, dflt in self.defaults.items()}

    def getconfig(self, name:str) -> ChainMap:
        "return a chainmap for a single object"
        name = self._objname(name)
        cur  = self.__get({name: self._objects[name]})[name]
        dfl  = self.__get({name: self._defaults[name]})[name]
        return ChainMap({j: k for j, k in cur.items() if k != dfl[j]}, dfl)

    @staticmethod
    def __get(dico)-> Dict[str, Dict[str, Any]]:
        "return a dict containing all objects info"
        get = lambda i: dict(i if isinstance(i, dict) else i.__dict__)
        out = {i: get(j) for i, j in dico.items()}
        for i in out.values():
            i.pop("name", None)
        return out

    def __update(self, key:str, name, kwa: Dict[str, Any]):
        "update a specific display and emits an event"
        name = self._objname(name)
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
