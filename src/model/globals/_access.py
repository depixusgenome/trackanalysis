#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Storing global properties"
from typing  import Optional
from abc     import ABC
from ._child import GlobalsChild, delete

class SingleMapAccess:
    "access to SingleMapController"
    PROPS    = ('items', 'default', 'defaults')
    value    = property(lambda self:        self.get(),
                        lambda self, val:   self.set(val),
                        lambda self:        self.pop())
    items    = property(lambda self:        self._map.items(self._base),
                        lambda self, val:   self.update(**val),
                        lambda self:        self._map.pop(*self.items))
    default  = property(lambda self:        self.getdefault(),
                        lambda self, val:   self.setdefault(val))
    defaults = property(None,
                        lambda self, val:   self.setdefaults(**val))

    _key               = ''
    _base              = property(lambda self: (self._key[:-1] if len(self._key) else ''))
    _map: GlobalsChild = None
    def __init__(self, _model, key):
        self.__dict__.update(_map = _model, _key = key)

    def __call__(self, *args, **kwargs):
        if self._key == '':
            raise TypeError("SingleMapAccess is not callable")
        else:
            key = self._base
            ind = key.rfind('.')
            val = self._map.get(key[:ind])
            return getattr(val, key[ind+1:])(*args, **kwargs)

    def __getattr__(self, name):
        return type(self)(self.__dict__['_map'], self._key+name+'.')

    def __getitem__(self, name):
        return (self._map.get(*name)     if isinstance(name, (tuple, list)) else
                self.__getattr__(name))

    def __eq__(self, other):
        return self.get() == other

    def __setattr__(self, name, value):
        if name[0] == '_' or name in SingleMapAccess.PROPS:
            return super().__setattr__(name, value)
        return self._map.update((self._key+name, value))

    __setitem__ = __setattr__

    def __delattr__(self, name):
        if name[0] == '_' or name in SingleMapAccess.PROPS:
            return super().__delattr__(name)
        return self._map.pop(self._key+name)

    def __delitem__(self, name):
        return self.pop(*name) if isinstance(name, (tuple, list)) else self.pop(name)

    def __kwargs(self, args, kwargs):
        if len(args) == 1 and isinstance(args[0], dict):
            kwargs.update(args[0])
        else:
            kwargs.update(args)
        return iter((self._key+i, j) for i, j in kwargs.items())

    def getdefault(self, *keys):
        "Calls default using the current base key"
        if len(keys) == 0:
            return self._map.getdefault(self._base)
        return self._map.getdefault(*(self._key+i for i in keys))

    def setdefault(self, arg):
        "Calls update using the current base key"
        return self._map.setdefaults((self._base, arg))

    def setdefaults(self, *args, version = 1, **kwargs):
        """
        Sets the defaults using the current base key.
        - *args*   is a sequence of pairs (key, value)
        - *kwargs* is similar.
        The keys in argument are appended to the current key.

        >> ctrl.keypress.setdefaults(('zoom', 'Ctrl-z'))
        >> assert ctrl.keypress.zoom == 'Ctrl-z'

        One can also do:

        >> ctrl.keypress.defaults = {'zoom': 'Ctrl-z', 'pan': 'Ctrl-p'}
        >> assert ctrl.keypress.zoom == 'Ctrl-z'

        Or, for a single key:

        >> ctrl.keypress.zoom.default = 'Ctrl-z'
        >> assert ctrl.keypress.zoom == 'Ctrl-z'
        """
        return self._map.setdefaults(*self.__kwargs(args, kwargs), version = version)

    def get(self, *keys, default = delete):
        "Calls get using the current base key"
        if len(keys) == 0:
            return self._map.get(self._base, default = default)
        elif len(keys) == 1 and keys[0] is Ellipsis:
            return self._map.get(self._base, ...)
        elif len(keys) == 2 and keys[1] is Ellipsis:
            return self._map.get(self._key+keys[0], ...)
        return self._map.get(*(self._key+i for i in keys), default = default)

    def getdict(self, *keys, default = delete, fullnames = True) -> dict:
        "Calls get using the current base key"
        if len(keys) == 1 and keys[0] is Ellipsis:
            vals = self._map.get(self._base, ..., default = default)
            lenb = len(self._base)
            if fullnames or lenb == 0:
                return vals
            lenb += 1
            return {i[lenb:]: j for i, j in vals.items()}
        else:
            fkeys = tuple(self._key+i for i in keys)
            vals  = self._map.get(*fkeys, default = default)
            return dict(zip(fkeys if fullnames else keys, vals))

    def getitems(self, *keys, default = delete, fullnames = False) -> dict:
        "Calls get using the current base key"
        return self.getdict(*keys, default = default, fullnames = fullnames)

    def set(self, arg):
        "Calls update using the current base key"
        return self._map.update({self._base: arg})

    def update(self, *args, **kwargs):
        """
        Calls update using the current base key.
        - *args*   is a sequence of pairs (key, value)
        - *kwargs* is similar.
        The keys in argument are appended to the current key.

        >> ctrl.keypress.update(('zoom', 'Ctrl-z'))
        >> assert ctrl.keypress.zoom == 'Ctrl-z'

        One can also do:

        >> ctrl.keypress.items = {'zoom': 'Ctrl-z', 'pan': 'Ctrl-p'}
        >> assert ctrl.keypress.zoom == 'Ctrl-z'

        Or, for a single key:

        >> ctrl.keypress.zoom.item = 'Ctrl-z'
        >> assert ctrl.keypress.zoom == 'Ctrl-z'
        """
        return self._map.update(*self.__kwargs(args, kwargs))

    def pop(self, *keys):
        "Calls get using the current base key"
        if len(keys) == 0:
            return self._map.pop(self._base)
        return self._map.pop(*(self._key+i for i in keys))

class BaseGlobalsAccess:
    "Contains all access to model items likely to be set by user actions"
    def __init__(self, ctrl, key, name):
        self._ctrl = ctrl
        self._name = name
        self._key  = key

    def _global(self, name):
        return getattr(self._ctrl, 'globals', self._ctrl).getGlobal(name)

    def __getattr__(self, key):
        if key[0] == '_':
            return super().__getattribute__(key)
        if key == 'root':
            return self._global(self._name)
        if key == 'plot':
            return self._global(self._name+'.plot')

        ctrl = self._global(self._name+self._key)
        return getattr(ctrl, key)

    __getitem__ = __getattr__

    def __setattr__(self, key, val):
        if key[0] == '_':
            return super().__setattr__(key, val)
        ctrl = self._global(self._name+self._key)
        return setattr(ctrl, key, val)

    __setitem__ = __setattr__

class GlobalsAccess(ABC):
    "Contains all access to model items likely to be set by user actions"
    def __init__(self, ctrl, key:str = None, **_) -> None:
        self.__model              = getattr(ctrl, '_GlobalsAccess__model', ctrl)
        self.__key: Optional[str] = getattr(ctrl, '_GlobalsAccess__key',  key)

    config  = property(lambda self: BaseGlobalsAccess(self.__model, self.__key, 'config'))
    css     = property(lambda self: BaseGlobalsAccess(self.__model, self.__key, 'css'))
    project = property(lambda self: BaseGlobalsAccess(self.__model, self.__key, 'project'))

__all__ = ['GlobalsAccess', 'SingleMapAccess', 'BaseGlobalsAccess']
