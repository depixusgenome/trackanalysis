#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
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
from    typing        import Callable, Optional
from    itertools     import product
import  inspect

import  anastore

from    model.globals import (GlobalsChild, GlobalsAccess, SingleMapAccess,
                              EventData, delete, Globals)
from    model.level   import PHASE
from    .event        import Controller
from    .action       import Action

class SingleMapAccessController(SingleMapAccess):
    "access to SingleMapController"
    def observe(self, *names, decorate = None, argstest = None):
        "observes items in the current root"
        if len(names) == 1 and isinstance(names[0], str):
            raise AttributeError('Missing observer function')
        elif len(names) == 1 and self._base != '':
            names = self._base, names[0]
        else:
            names = tuple((self._key+i if isinstance(i, str) else i) for i in names)
        self._map.observe(*names, decorate = decorate, argstest = argstest)

class SingleMapController(Controller):
    "Dictionnary with defaults values. It can be reset to these."
    __slots__ = ('__items',)
    def __init__(self, mdl:GlobalsChild, **kwargs) -> None:
        super().__init__(**kwargs)
        self.__items = mdl # type: GlobalsChild

    def setdefaults(self, *args, version = None, **kwargs):
        "adds defaults to the config"
        self.__items.setdefaults(*args, version = version, **kwargs)

    def reset(self, base = ''):
        "resets to default values"
        return self.update(dict.fromkeys(self.__items.keys(base), delete))

    def update(self, *args, **kwargs) -> EventData:
        "updates keys or raises NoEmission"
        ret = self.__items.update(*args, **kwargs)
        if ret is not None:
            return self.handle("globals."+ret.name, self.outastuple, (ret,))
        return ret

    def pop(self, *args):
        "removes view information"
        return self.update(dict.fromkeys(args, delete))

    @property
    def name(self) -> str:
        "returns the name of the root"
        return self.__items.name

    def observe(self, *names,   # pylint: disable=arguments-differ
                decorate = None,
                argstest = None):

        "observes items in the current root"
        fcn = next((i for i in names if not isinstance(i, str)), None)
        if fcn is None:
            raise AttributeError('Missing observer function')

        elif sum(1 for i in names if not isinstance(i, str)) > 1:
            raise AttributeError('Too many observer functions')

        attrs = frozenset(i for i in names if isinstance(i, str) and len(i))
        if not self.__npars(fcn):
            if len(attrs) == 0:
                observer = lambda itms: fcn()
            else:
                observer = lambda itms: attrs.isdisjoint(itms) or fcn()
        else:
            if len(attrs) == 1:
                attr     = next(iter(attrs))
                observer = lambda itms: fcn(itms[attr]) if attr in itms else None
            elif len(attrs) == 0:
                observer = fcn
            else:
                observer = lambda itms: attrs.isdisjoint(itms) or fcn(itms)
        super().observe('globals.'+self.__items.name, observer,
                        decorate = decorate,
                        argstest = argstest)

    def keys(self, base = ''):
        "returns all keys starting with base"
        return self.__items.keys(base)

    def values(self, base = ''):
        "returns all values with keys starting with base"
        return self.__items.values(base)

    def items(self, base = ''):
        "returns all items with keys starting with base"
        return self.__items.items(base)

    def get(self, *keys, default = delete):
        "returns values associated to the keys"
        return self.__items.get(*keys, default = default)

    @staticmethod
    def __npars(fcn) -> bool:
        params = [i for i, j in inspect.signature(fcn).parameters.items()
                  if j.kind == j.POSITIONAL_OR_KEYWORD and j.default is j.empty]
        if len(params) == 0:
            return False
        elif len(params) == 1:
            return next(iter(params)) not in ('cls', 'self')
        elif len(params) == 2:
            assert next(iter(params)) in ('cls', 'self')
            return True
        assert False
        return False

class BaseGlobalsController(Controller):
    """
    Controller class for global values.
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
        self.__model = Globals()
        self.__maps  = dict()

    def addGlobalMap(self, key, *args, **kwargs):
        "adds a map"
        val  = getattr(self.__model.addGlobalMap(key, *args, **kwargs), '_map')
        self.__maps[key] = SingleMapController(val, handlers = self._handlers)
        return SingleMapAccessController(self.__maps[key], '')

    def removeGlobalMap(self, key):
        "removes a map"
        self.__maps.pop(key)
        self.__model.removeGlobalMap(key)

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
            return SingleMapAccessController(self.__maps[key], '')
        return self.__maps[key].get(*args, default = default)

    def writeconfig(self, configpath: Callable,
                    patchname = 'config',
                    index     = 0,
                    overwrite = True,
                    ** kwa):
        """
        Writes up the user preferences.

        If *overwrite* is *False*, the preferences are first read from file, then
        written again. Notwithstanding version patches, this is a no-change operation.
        """
        css = self.getGlobal('css').config.getdict(..., fullnames = False)
        self.__model.writeconfig(configpath, anastore, patchname,
                                 index, overwrite, **kwa, **css)

    def readconfig(self, configpath, patchname = 'config'):
        "Sets-up the user preferences"
        cnf = self.__model.readconfig(configpath, anastore, patchname)
        if cnf is None or len(cnf) == 0:
            return

        with Action(self):
            for root, values in cnf.items():
                self.__maps[root].update(values)

class GlobalsController(BaseGlobalsController):
    """
    Controller class for global values with initial defaults
    """
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        for suff, name in product(('', '.plot'), ('project', 'css', 'config')):
            self.addGlobalMap(name+suff)

        self.getGlobal('project').message.default = ''
        self.getGlobal('project.plot').delayed.default = False

        css = self.getGlobal('css')
        css.config.defaults = {'indent': 4, 'ensure_ascii': False, 'sort_keys': True}

        cnf = self.getGlobal('config')
        cnf.catcherror.default = False
        cnf.phase.defaults     = PHASE.__dict__
        cnf.tasks.defaults     = {'processors':  'control.processor.Processor',
                                  'io.open':    ('anastore.control.AnaIO',
                                                 'control.taskio.GrFilesIO',
                                                 'control.taskio.TrackIO'),
                                  'io.save':    ('anastore.control.ConfigAnaIO',),
                                  'clear':      True
                                 }

    def access(self, key: Optional[str] = None) -> GlobalsAccess:
        "returns a GlobalsAccess to a given map"
        return GlobalsAccess(self, key)

    def __undos__(self):
        "yields all undoable user actions"
        def _onglobals(items):
            vals = {i: j.old for i, j in items.items()}
            if len(vals):
                return lambda: self.updateGlobal(items.name, **vals)
        maps = self._BaseGlobalsController__maps # pylint: disable=protected-access,no-member
        yield tuple('globals.' + i for i in maps
                    if not i.startswith('project')) + (_onglobals,)
