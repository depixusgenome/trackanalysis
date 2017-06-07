#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Utils for easily  with the JS side of the view"
from    typing      import (Generic, TypeVar, Type, # pylint: disable=unused-import
                            Callable, Iterator, Optional, Sequence, Union, Any)
from    collections import ChainMap, namedtuple
import  inspect

from    utils.logconfig import getLogger
LOGS    = getLogger(__name__)

_CNT    = 2
_m_none = type('_m_none', (), {}) # pylint: disable=invalid-name
T       = TypeVar('T')

EventPair = namedtuple('EventPair', ['old', 'value'])
delete    = type('delete', tuple(), dict())    # pylint: disable=invalid-name
class EventData(dict):
    "All data provided to the event"
    empty = delete
    def __init__(self, root, *args, **kwargs):
        self.name = root
        super().__init__(*args, **kwargs)

def _tokwargs(args, kwargs):
    if len(args) == 1 and isinstance(args[0], dict):
        kwargs.update(args[0])
    else:
        kwargs.update(args)
    return kwargs

class SingleMapAccess:
    "access to SingleMapController"
    PROPS    = ('items', 'default', 'defaults')
    value    = property(lambda self:        self.get(),
                        lambda self, val:   self.set(val),
                        lambda self:        self.pop())
    items    = property(lambda self:        self._map.items(self._base),
                        lambda self, val:   self.update(**val),
                        lambda self:        self._map.pop(*self.items))
    default  = property(None,
                        lambda self, val:   self.setdefault(val))
    defaults = property(None,
                        lambda self, val:   self.setdefaults(**val))

    _key  = ''      # type: str
    _base = property(lambda self: (self._key[:-1] if len(self._key) else ''))
    _map  = None    # type: GlobalsChild
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
        if name[0] == '_' or name in SingleMapAccess.PROPS:
            return super().__getattribute__(name)
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

class GlobalsChild(ChainMap): # pylint: disable=too-many-ancestors
    "Dictionnary with defaults values. It can be reset to these."
    __NAME    = 'の'
    __slots__ = ('__name',)
    def __init__(self, name:str, parent: Optional['GlobalsChild'] = None) -> None:
        maps = [dict() for i in range(_CNT)] # type: ignore
        if parent is not None:
            # pylint:disable=protected-access
            maps.append(parent) # type: ignore
        super().__init__(*maps)
        self.__name  = name # type: str

    def setdefaults(self, *args, version = None, **kwargs):
        "adds defaults to the config"
        self.maps[1 if version is None else version].update(**_tokwargs(args, kwargs))

    def reset(self):
        "resets to default values"
        self.pop(*self.maps[1].keys())

    def update(self, *args, **kwargs) -> Optional[EventData]: # type: ignore
        "updates keys or raises NoEmission"
        ret = EventData(self.__name)
        for key, val in _tokwargs(args, kwargs).items():
            old     = super().get(key, delete)
            default = self.maps[1].get(key, delete)
            if default is delete:
                if len(self.maps) > 2:
                    default = self.maps[-1].get(key, delete)
                if default is delete:
                    raise KeyError("Default value must be set first "
                                   +str((self.__name, key)))
            elif val is delete or val == default:
                super().pop(key, None)
            else:
                super().__setitem__(key, val)

            if old != val:
                ret[key] = EventPair(old, val)

        if len(ret) > 0:
            return ret
        return None

    @property
    def name(self) -> str:
        "returns the name of the root"
        return self.__name

    def pop(self, *args):                       # pylint: disable=arguments-differ
        "removes view information"
        return self.update(dict.fromkeys(args, delete))

    def keys(self, base = ''):                  # pylint: disable = arguments-differ
        "returns all keys starting with base"
        return iter(key for key in super().keys() if key.startswith(base))

    def values(self, base = ''):                # pylint: disable = arguments-differ
        "returns all values with keys starting with base"
        return iter(val for key, val in super().items() if key.startswith(base))

    def items(self, base = ''):                 # pylint: disable = arguments-differ
        "returns all items with keys starting with base"
        return iter(key for key in super().items() if key[0].startswith(base))

    def get(self, *keys, default = delete):     # pylint: disable=arguments-differ
        "returns values associated to the keys"
        if len(keys) == 2 and keys[1] is Ellipsis:
            root = keys[0]
            base = keys[0]+'.'
            return {i: j for i, j in super().items() if i == root or i.startswith(base)}

        if default is not delete:
            if len(keys) == 1:
                return super().get(keys[0], default)

            if isinstance(default, list):
                return iter(super().get(key, val) for key, val in zip(keys, default))

            return iter(super().get(key, default) for key in keys)

        if len(keys) == 1:
            return self.__getitem__(keys[0])
        return iter(self.__getitem__(key) for key in keys)

    def __setitem__(self, key, val):
        return self.update({key: val})

    def __getstate__(self):
        info = {self.__NAME: self.__name}
        info.update(self.maps[0])
        return info

    def __setstate__(self, info):
        self.__name = info.pop(self.__NAME)
        self.maps[0].update(info)

def getglobalsproperties(cls:Type[T], obj) -> Iterator[T]:
    "iterates over properties"
    pred = lambda i: isinstance(i, cls)
    yield from (i for _, i in inspect.getmembers(type(obj), pred))

class ConfigRootProperty(Generic[T]):
    "a property which links to the config"
    OBSERVERS = ('config.root',)
    def __init__(self, key:str) -> None:
        self.key = key

    def setdefault(self, obj, value:T, items:Optional[dict] = None, **kwa):
        "initializes the property stores"
        if items is not None:
            kwa.update(**items)
        obj.config.root[self.key].default  = value
        obj.config.root[self.key].defaults = kwa

    def __get__(self, obj, tpe) -> T:
        return self if obj is None else obj.config.root[self.key].get()

    def __set__(self, obj, val:T) -> T:
        return self if obj is None else obj.config.root[self.key].set(val)

class ProjectRootProperty(Generic[T]):
    "a property which links to the project"
    OBSERVERS = ('project.root',)
    def __init__(self, key:str) -> None:
        self.key = key

    def setdefault(self, obj, value:T, items:Optional[dict] = None, **kwa):
        "initializes the property stores"
        if items is not None:
            kwa.update(**items)
        obj.project.root[self.key].default  = value
        obj.project.root[self.key].defaults = kwa

    def __get__(self, obj, tpe) -> T:
        return self if obj is None else obj.project.root[self.key].get()

    def __set__(self, obj, val:T) -> T:
        return self if obj is None else obj.project.root[self.key].set(val)

class ConfigProperty(Generic[T]):
    "a property which links to the root config"
    OBSERVERS = ('config',)
    def __init__(self, key:str) -> None:
        self.key = key

    def setdefault(self, obj, value:T, items:Optional[dict] = None, **kwa):
        "initializes the property stores"
        if items is not None:
            kwa.update(**items)
        obj.config[self.key].default  = value
        obj.config[self.key].defaults = kwa

    def __get__(self, obj, tpe) -> T:
        return self if obj is None else obj.config[self.key].get()

    def __set__(self, obj, val:T) -> T:
        return obj.config[self.key].set(val)

class BeadProperty(Generic[T]):
    "a property which links to the config and the project"
    OBSERVERS = 'config', 'project'
    def __init__(self, key:str) -> None:
        self.key = key

    def setdefault(self, obj, value:T, items:Optional[dict] = None, **kwa):
        "initializes the property stores"
        if items is not None:
            kwa.update(**items)
        obj.project[self.key].default = None
        obj.project[self.key].set({})
        obj.config[self.key].default  = value
        obj.config[self.key].defaults = kwa

    @classmethod
    def clear(cls, obj):
        "clears the property stores"
        for prop in getglobalsproperties(cls, obj):
            obj.project[prop.key].get().clear()

    def __get__(self, obj, tpe) -> T:
        if obj is None:
            return self # type: ignore
        value = obj.project[self.key].get().get(obj.bead, _m_none)
        if value is not _m_none:
            return value
        return obj.config[self.key].get()

    def __set__(self, obj, val:T) -> T:
        cache = dict(obj.project[self.key].get())
        if val == obj.config[self.key].get():
            cache.pop(obj.bead, None)
        else:
            cache[obj.bead] = val

        obj.project[self.key].set(cache)
        return val

class _GlobalsAccess:
    def __init__(self, ctrl, key, name):
        self._ctrl = ctrl
        self._name = name
        self._key  = key

    def __getattr__(self, key):
        if key[0] == '_':
            return super().__getattribute__(key)
        if key == 'root':
            return self._ctrl.getGlobal(self._name)
        if key == 'plot':
            return self._ctrl.getGlobal(self._name+'.plot')

        ctrl = self._ctrl.getGlobal(self._name+self._key)
        return getattr(ctrl, key)

    __getitem__ = __getattr__

    def __setattr__(self, key, val):
        if key[0] == '_':
            return super().__setattr__(key, val)
        ctrl = self._ctrl.getGlobal(self._name+self._key)
        return setattr(ctrl, key, val)

    __setitem__ = __setattr__

class GlobalsAccess:
    "Contains all access to model items likely to be set by user actions"
    def __init__(self, ctrl, key:Optional[str] = None, **_) -> None:
        self.__model = getattr(ctrl, '_GlobalsAccess__model', ctrl) # type: Any
        self.__key   = getattr(ctrl, '_GlobalsAccess__key',  key)  # type: Optional[str]

    @property
    def config(self):
        "returns an access to config"
        return _GlobalsAccess(self.__model, self.__key, 'config')

    @property
    def css(self):
        "returns an access to css"
        return _GlobalsAccess(self.__model, self.__key, 'css')

    @property
    def project(self):
        "returns an access to project"
        return _GlobalsAccess(self.__model, self.__key, 'project')

class Globals:
    """
    container for global values.
    These can be accessed using a main key and secondary keys:

    >> # Get the secondary key 'keypress.pan.x' in 'plot'
    >> ctrl.getGlobal('plot').keypress.pan.x.low.get()

    >> # Get the secondary keys 'keypress.pan.x.low' and 'high'
    >> ctrl.getGlobal('plot').keypress.pan.x.get('low', 'high')

    >> # Get secondary keys starting with 'keypress.pan.x'
    >> ctrl.getGlobal('plot').keypress.pan.x.items
    """
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.__maps  = dict()

    def items(self):
        "access to all maps"
        return self.__maps.items()

    def addGlobalMap(self, key, *args, **kwargs):
        "adds a map"
        if key not in self.__maps:
            parent           = self.__maps[key[:key.rfind('.')]] if '.' in key else None
            self.__maps[key] = GlobalsChild(key, parent)

        self.__maps[key].setdefaults(*args, **kwargs)
        return SingleMapAccess(self.__maps[key], '')

    def removeGlobalMap(self, key):
        "removes a map"
        self.__maps.pop(key)

    def setGlobalDefaults(self, key, **kwargs):
        "sets default values to the map"
        self.__maps[key].setdefaults(**kwargs)

    def updateGlobal(self, key, *args, **kwargs) -> dict:
        "updates view information"
        return self.__maps[key].update(*args, **kwargs)

    def deleteGlobal(self, key, *args):
        "removes view information"
        return self.__maps[key].pop(*args)

    def getGlobal(self, key, *args, default = delete):
        "returns values associated to the keys"
        if len(args) == 0 or len(args) == 1 and args[0] == '':
            return SingleMapAccess(self.__maps[key], '')
        return self.__maps[key].get(*args, default = default)

    def writeconfig(self, configpath:Callable, protocol, # pylint: disable=too-many-arguments
                    patchname = 'config',
                    index     = 0,
                    overwrite = True,
                    **kwa):
        """
        Writes up the user preferences.

        If *overwrite* is *False*, the preferences are first read from file, then
        written again. Notwithstanding version patches, this is a no-change operation.
        """
        maps = None if overwrite else self.readconfig(configpath, protocol, patchname)
        if maps is None:
            maps = {i: j.maps[index] for i, j in self.__maps.items() if 'project' not in i}
            maps = {i: j for i, j in maps.items() if len(j)}

        path = configpath(protocol.version(patchname))
        path.parent.mkdir(parents = True, exist_ok = True)
        path.touch(exist_ok = True)

        protocol.dump(maps, path, patch = patchname, **kwa)

    def readconfig(self, configpath, protocol, patchname = 'config') -> Optional[dict]:
        "Sets-up the user preferences"
        cnf   = None
        first = True
        for version in protocol.iterversions(patchname):
            path = configpath(version)
            if not path.exists():
                continue
            try:
                cnf = protocol.load(path, patch = patchname)
            except Exception as exc: # pylint: disable=broad-except
                LOGS.warning("Failed loading %s", path, exc_info = exc)
                first = False
                continue
            (LOGS.debug if first else LOGS.info)("Loaded %s", path)
            break

        if cnf is None:
            return None

        for root in frozenset(cnf) - frozenset(self.__maps):
            cnf.pop(root)

        for root, values in tuple(cnf.items()):
            for key in frozenset(values) - frozenset(self.__maps[root]):
                values.pop(key)
            if len(values) == 0:
                cnf.pop(root)
        return cnf
