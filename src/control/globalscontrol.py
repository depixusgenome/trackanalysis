#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"""
All things global:
    - current track
    - current task
    - current view ...

A global map can be added by any view, although one should take care not
to mix both project-specific and project-generic info. For example, there
are different maps for storing the key mappings from the current track being
displayed.

Maps default values are memorized. The user can change the values then return
to the default settings.

A child map is a specialization of a parent map. It is specidied using a key in
the form of "parent.child". A child map has access to all parent items. It can
overload the values but cannot change the parent's.

Such a parent/child relationship can be used to specialize default values. For
example, the "plot" map will contain items for all plot types. The "plot.bead"
map only needs specify those default values that should be changed for this type
of plot.
"""
from typing         import Dict, Union          # pylint: disable=unused-import
from collections    import namedtuple, ChainMap
from .event         import Controller

ReturnPair = namedtuple('ReturnPair', ['old', 'value'])
delete     = type('delete', tuple(), dict())    # pylint: disable=invalid-name

def _tokwargs(args, kwargs):
    if len(args) == 1 and isinstance(args[0], dict):
        kwargs.update(args[0])
    else:
        kwargs.update(args)
    return kwargs

class _MapGetter:
    value    = property(lambda self:        self._ctrl.get(self._key),
                        lambda self, val:   self._ctrl.update((self._key, val)),
                        lambda self:        self._ctrl.pop(self._key))
    values   = property(lambda self:        self._ctrl.values(self._key),
                        lambda self, val:   self.update(**val),
                        lambda self:        self._ctrl.pop(*self.values))
    defaults = property(None,
                        lambda self, val:   self.setdefaults(**val))

    _key  = ''      # type: str
    _ctrl = None    # type: DefaultsMap
    def __init__(self, ctrl, key):
        self.__dict__.update(_ctrl = ctrl, _key = key)

    def __getattr__(self, name):
        if name[0] == '_' or name in ('value', 'values', 'defaults'):
            return super().__getattribute__(name)
        elif self._key == '':
            return _MapGetter(self.__dict__['_ctrl'], name)
        else:
            self._key += '.'+name
            return self

    def __getitem__(self, name):
        if isinstance(name, (tuple, list)):
            return self._ctrl.get(*name)
        else:
            return self.__getattr__(name)

    def __eq__(self, other):
        return self._ctrl.get(self._key) == other

    def __setattr__(self, name, value):
        if name[0] == '_' or name in ('value', 'values', 'defaults'):
            return super().__setattr__(name, value)
        else:
            return self._ctrl.update((self._key+'.'+name, value))

    __setitem__ = __setattr__

    def __delattr__(self, name):
        if name[0] == '_' or name in ('value', 'values', 'defaults'):
            return super().__delattr__(name)
        else:
            return self._ctrl.pop(self._key+'.'+name)

    def __delitem__(self, name):
        if isinstance(name, (tuple, list)):
            return self.pop(*name)
        else:
            return self.pop(name)


    def __kwargs(self, args, kwargs):
        key   = self._key
        items = _tokwargs(args, kwargs).items()
        if len(key) == 0:
            return items
        else:
            return ((self._key+'.'+i, j) for i, j in items)

    def setdefaults(self, *args, version = 1, **kwargs):
        u"Calls update using the current base key"
        return self._ctrl.setdefaults(*self.__kwargs(args, kwargs), version = version)

    def update(self, *args, **kwargs):
        u"Calls update using the current base key"
        return self._ctrl.update(*self.__kwargs(args, kwargs))

    def pop(self, *keys):
        u"Calls get using the current base key"
        return self._ctrl.pop(*(self._key+'.'+i for i in keys))

    def get(self, *keys, default = delete):
        u"Calls get using the current base key"
        return self._ctrl.get(*(self._key+'.'+i for i in keys), default = default)

class DefaultsMap(Controller):
    u"Dictionnary with defaults values. It can be reset to these."
    _CNT = 2
    def __init__(self, name, parent = None, **kwargs):
        maps = tuple(dict() for i in range(self._CNT))
        if parent is not None:
            maps += (parent,)

        super().__init__(**kwargs)
        self.__name  = "globals."+name
        self.__items = ChainMap(*maps)

    def createChild(self, name, **kwargs):
        u"returns a child map"
        return DefaultsMap(name, parent = self.__items, **kwargs)

    def setdefaults(self, *args, version = 1, **kwargs):
        u"adds defaults to the config"
        self.__items.maps[version].update(**_tokwargs(args, kwargs))

    def reset(self, version = None):
        u"resets to default values"
        if version is None:
            version = -1
        for i in range(version):
            self.__items.maps[i].clear()

    def update(self, *args, **kwargs) -> dict:
        u"updates keys or raises NoEmission"
        ret = dict(empty = delete) # type: Dict[str,Union[type,ReturnPair]]
        for key, val in _tokwargs(args, kwargs).items():
            old = self.__items.get(key, delete)
            if val is delete:
                self.__items.pop(key, None)
            else:
                self.__items[key] = val

            if old != val:
                ret[key] = ReturnPair(old, val)

        if len(ret):
            return self.handle(self.__name, self.outasdict, ret)

    def pop(self, *args):
        u"removes view information"
        return self.update(dict.fromkeys(args, delete))

    def keys(self, base = ''):
        u"returns all keys starting with base"
        return iter(key for key in self.__items if key.startswith(base))

    def values(self, base = ''):
        u"returns all values with keys starting with base"
        return iter(val for key, val in self.__items.items() if key.startswith(base))

    def items(self, base = ''):
        u"returns all items with keys starting with base"
        return iter(key for key in self.__items.items() if key[0].startswith(base))

    def get(self, *keys, default = delete):
        u"returns values associated to the keys"
        if default is not delete:
            if len(keys) == 1:
                return self.__items.get(keys[0], default)

            elif isinstance(default, list):
                return iter(self.__items.get(key, val)
                            for key, val in zip(keys, default))
            else:
                return iter(self.__items.get(key, default) for key in keys)
        else:
            if len(keys) == 1:
                return self.__items[keys[0]]
            return iter(self.__items[key] for key in keys)

class GlobalsController(Controller):
    u"""
    Controller class for global values.
    These can be accessed using a main key and secondary keys:

    >> # Get the secondary key 'keypress.pan.x' in 'plot'
    >> ctrl.getGlobal('plot').keypress.pan.x.low.value

    >> # Get the secondary keys 'keypress.pan.x.low' and 'high'
    >> ctrl.getGlobal('plot').keypress.pan.x.get('low', 'high')

    >> # Get secondary keys starting with 'keypress.pan.x'
    >> ctrl.getGlobal('plot').keypress.pan.x.values
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.__maps = dict()
        self.addGlobalMap('css').button.width = 90
        self.addGlobalMap('config').keypress.defaults = {'undo' : "Control-z",
                                                         'redo' : "Control-y",
                                                         'open' : "Control-o",
                                                         'save' : "Control-s",
                                                         'quit' : "Control-q"}
        def _gesture(meta):
            return {'speed'   : .2,
                    'activate': meta,
                    'x.low'   : meta+'ArrowLeft',
                    'x.high'  : meta+'ArrowRight',
                    'y.low'   : meta+'ArrowDown',
                    'y.high'  : meta+'ArrowUp'}

        item = self.addGlobalMap('config.plot')
        item.tools              = 'xpan,box_zoom,reset,save'
        item.boundary.overshoot = .005
        item.keypress.reset     = ' '
        item.keypress.pan       =  _gesture('')
        item.keypress.zoom      =  _gesture('Shift')

        self.addGlobalMap('current')
        self.addGlobalMap('current.plot')

    def addGlobalMap(self, key, *args, **kwargs):
        u"adds a map"
        if '.' in key:
            parent = self.__maps[key[:key.rfind('.')]]
            self.__maps[key] = parent.createChild(key, handlers = self._handlers)
        else:
            self.__maps[key] = DefaultsMap(key, handlers = self._handlers)

        self.__maps[key].setdefaults(*args, **kwargs)
        return _MapGetter(self.__maps[key], '')

    def removeGlobalMap(self, key):
        u"removes a map"
        self.__maps.pop(key)

    def setGlobalDefaults(self, key, **kwargs):
        u"sets default values to the map"
        self.__maps[key].setdefaults(**kwargs)

    def updateGlobal(self, key, *args, **kwargs) -> dict:
        u"updates view information"
        return self.__maps[key].update(*args, **kwargs)

    def deleteGlobal(self, key, *args):
        u"removes view information"
        return self.__maps[key].pop(*args)

    def getGlobal(self, key, *args, default = delete):
        u"returns values associated to the keys"
        if len(args) == 0:
            return _MapGetter(self.__maps[key], '')
        return self.__maps[key].get(*args, default = default)
