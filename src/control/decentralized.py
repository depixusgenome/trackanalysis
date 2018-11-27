#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Decentralized controller"
import pickle
from  functools         import partial
from  collections       import ChainMap
from  contextlib        import contextmanager
from  copy              import deepcopy, copy
from  typing            import Dict, Any, TypeVar

import numpy            as     np
import pandas           as     pd

from  utils             import initdefaults
from  utils.logconfig   import getLogger
from  .event            import Controller
LOGS    = getLogger(__name__)
DELETE  = type('DELETE', (), {})
Missing = type("Missing")

def _isdiff(left, right):
    if type(left) is not type(right):
        return True

    if hasattr(left, '__getstate__'):
        left, right = left.__getstate__(), right.__getstate__()

    if isinstance(left, dict):
        return set(left) != set(right) or any(_isdiff(right[i], j) for i, j in left.items())

    return left != right and pickle.dumps(left) != pickle.dumps(right)

def _good(model, i, j):
    obj = getattr(model, i, Missing)
    if obj is Missing:
        return False

    # pylint: disable=unidiomatic-typecheck
    if type(obj) != type(j) or (isinstance(obj, dict) and set(obj) != set(j)):
        return True

    if any(isinstance(k, (pd.DataFrame, np.ndarray, dict)) for k in (j, obj)):
        return pickle.dumps(obj) != pickle.dumps(j)

    try:
        return obj != j
    except ValueError:
        return True # numpy error

def updatemodel(self, model, kwa, force = False, deflt = None):
    "update the model"
    kwa = {i:j for i, j in kwa.items() if _good(model, i, j)}

    if len(kwa) == 0 and not force:
        return None

    if callable(getattr(model, 'configure', None)):
        dmdl = model.__getstate__()

        old  = {i: dmdl[i] for i in kwa}
        rem  = {i: dmdl[i] for i,j in kwa.items() if j is DELETE}
        if rem:
            ddef = (model.__class__() if deflt is None else deflt).__getstate__()
            kwa.update({i: ddef[i] for i, j in kwa.items() if j is DELETE})
        model.configure(kwa)
    else:
        old = {i: getattr(model, i) for i in kwa}
        rem = {i: getattr(model, i) for i,j in kwa.items() if j is DELETE}
        if rem:
            deflt = model.__class__() if deflt is None else deflt
            kwa.update({i: getattr(deflt, i) for i, j in kwa.items() if j is DELETE})
        for i, j in kwa.items():
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

class Indirection:
    "descriptor for accessing a given model"
    __slots__ = ('_ctrl', '_attr')
    def __init__(self):
        self._ctrl: str = ""
        self._attr: str = ""

    def __set_name__(self, _, attr):
        self._attr = attr

    def observe(self, ctrl, inst, *args, **kwa):
        "add the model to the controller"
        attr = inst.__dict__[self._attr]
        return getattr(ctrl, self._ctrl).observe(attr, *args, **kwa)

    def update(self, inst, **value):
        "update the model"
        attr = inst.__dict__[self._attr]
        self.controller(getattr(inst, '_ctrl')).update(attr, **value)

    def controller(self, ctrl):
        "get the controller"
        return getattr(ctrl, self._ctrl)

    def __get__(self, inst, owner):
        if inst is None:
            return self
        return self.controller(getattr(inst, '_ctrl')).model(inst.__dict__[self._attr])

    def __set__(self, inst, value):
        if isinstance(value, dict):
            attr = inst.__dict__[self._attr]
            self.controller(getattr(inst, '_ctrl')).update(attr, **value)
        else:
            assert inst.__dict__.get(self._attr, value.name) == value.name
            ctrl       = type(value).__name__.lower()
            self._ctrl = ("display" if any(i in ctrl for i in ("display", "store")) else
                          "theme")
            inst.__dict__[self._attr] = value.name
            self.controller(getattr(inst, '_ctrl')).add(value, noerase = False)

ObjType = TypeVar("ObjType")
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

    def add(self, obj: ObjType, noerase = True) -> ObjType:
        "add a model to be updated & observed through this controller"
        name = self._objname(obj)
        if name in self._objects:
            if noerase and self.model(name) is not obj:
                raise KeyError(f"key already registered: {name}")
            cur = self.model(name)
            if not isinstance(cur, type(obj)):
                raise TypeError(f"key already registered to a different type: {name}")
            return cur
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
        out   = {i: ChainMap({j: k for j, k in right[i].items() if _isdiff(k, dflt[j])}, dflt)
                 for i, dflt in self.defaults.items()}
        for i, j in out.items():
            if len(j.maps[0]) == 0:
                continue
            fcn = getattr(type(self._defaults[i]), "__config__", None)
            if callable(fcn):
                fcn(j)
        return out

    def getconfig(self, name:str) -> ChainMap:
        "return a chainmap for a single object"
        name = self._objname(name)
        cur  = self.__get({name: self._objects[name]})[name]
        dfl  = self.__get({name: self._defaults[name]})[name]
        out  = ChainMap({j: k for j, k in cur.items() if k != dfl[j]}, dfl)
        if len(out.maps[0]):
            fcn  = getattr(type(self._defaults[name]), "__config__", None)
            if callable(fcn):
                fcn(out)
        return out

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

    def __undos__(self, wrapper):
        @wrapper
        def _undo_method(control = None, model = None, old = None, **_):
            dflt = control.model(model, True) is model
            return partial(control.update, model, dflt, **old)

        self.observe(*self._objects.keys(), _undo_method)
