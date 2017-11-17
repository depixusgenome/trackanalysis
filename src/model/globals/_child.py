#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Storing global properties"
from    typing      import Dict, List, Optional, cast # pylint: disable=unused-import
from    collections import ChainMap, namedtuple

_CNT      = 2
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

class GlobalsChild(ChainMap): # pylint: disable=too-many-ancestors
    "Dictionnary with defaults values. It can be reset to these."
    __NAME    = 'の'
    __slots__ = ('__name',)
    def __init__(self, name:str, parent: 'GlobalsChild' = None) -> None:
        maps = [dict() for i in range(_CNT)] # type: List[Dict]
        if parent is not None:
            maps.append(cast(Dict, parent))
        super().__init__(*maps)
        self.__name = name

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
