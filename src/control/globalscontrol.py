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
import  inspect

import  anastore

from    model.globals import (GlobalsChild, GlobalsAccess, SingleMapAccess,
                              EventData, delete, Globals)
from    model.level   import PHASE
from    .event        import Controller
from    .action       import Action

class SingleMapAccessController(SingleMapAccess):
    "access to SingleMapController"
    def observe(self, attrs, fcn = None): # pylint: disable=arguments-differ
        "observes items in the current root"
        if fcn is None:
            self._map.observe(self._base, attrs)

        elif isinstance(attrs, str):
            self._map.observe(self._key+attrs, fcn)
        else:
            self._map.observe(tuple(self._key+i for i in attrs), fcn)

class SingleMapController(Controller):
    "Dictionnary with defaults values. It can be reset to these."
    __slots__ = '__items',
    def __init__(self, mdl:GlobalsChild, **kwargs) -> None:
        super().__init__(**kwargs)
        self.__items = mdl # type: GlobalsChild

    def setdefaults(self, *args, version = None, **kwargs):
        "adds defaults to the config"
        self.__items.setdefaults(*args, version = version, **kwargs)

    def reset(self):
        "resets to default values"
        self.__items.pop()

    def update(self, *args, **kwargs) -> EventData:
        "updates keys or raises NoEmission"
        ret = self.__items.update(*args, **kwargs)
        if ret is not None:
            return self.handle("globals."+self.__items.name, self.outastuple, (ret,))
        return ret

    def pop(self, *args):
        "removes view information"
        return self.__items.update(dict.fromkeys(args, delete))

    @property
    def name(self) -> str:
        "returns the name of the root"
        return self.__items.name

    def observe(self, attrs, fcn = None): # pylint: disable=arguments-differ
        "observes items in the current root"
        if attrs == '':
            attrs, fcn = fcn, None
        elif fcn == '':
            fcn = None

        if fcn is None:
            if not callable(attrs):
                raise TypeError()
            observer = attrs
        else:
            if callable(attrs):
                fcn, attrs = attrs, fcn

            if len(attrs) == 1 and not isinstance(attrs, str):
                attrs = attrs[0]

            npars = self.__npars(fcn)
            if isinstance(attrs, str):
                def _wrap(items):
                    if attrs in items:
                        if npars:
                            fcn(items[attrs])
                        else:
                            fcn()
                observer = _wrap
            else:
                def _wrap(items):
                    if any(i in items for i in attrs):
                        if npars:
                            fcn(items)
                        else:
                            fcn()
                observer = _wrap

        super().observe('globals.'+self.__items.name, observer)

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
        params = inspect.signature(fcn).parameters
        if len(params) == 0:
            return False
        elif len(params) == 1:
            return next(iter(params)) not in ('cls', 'self')
        elif len(params) == 2:
            assert next(iter(params)) in ('cls', 'self')
            return True
        assert False
        return False

class GlobalsController(Controller):
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
        self.addGlobalMap('css').button.defaults = {'width': 90, 'height': 20}
        self.addGlobalMap('css').config.defaults = {'indent':       4,
                                                    'ensure_ascii': False,
                                                    'sort_keys':    True}
        self.addGlobalMap('css').input .defaults = {'width': 90, 'height': 20}
        self.addGlobalMap("css.plot")
        self.addGlobalMap('config').keypress.defaults = {'undo' : "Control-z",
                                                         'redo' : "Control-y",
                                                         'open' : "Control-o",
                                                         'save' : "Control-s",
                                                         'quit' : "Control-q",
                                                         'beadup': 'PageUp',
                                                         'beaddown': 'PageDown'}
        self.getGlobal('config').phase.defaults = PHASE.__dict__

        tasks = self.getGlobal('config').tasks
        tasks.defaults = {'processors':  'control.processor.Processor',
                          'io.open':    ('anastore.control.AnaIO',
                                         'control.taskio.GrFilesIO',
                                         'control.taskio.TrackIO'),
                          'io.save':    ('anastore.control.AnaIO',),
                          'clear':      True
                         }

        def _gesture(meta):
            return {'rate'    : .2,
                    'activate': meta[:-1],
                    'x.low'   : meta+'ArrowLeft',
                    'x.high'  : meta+'ArrowRight',
                    'y.low'   : meta+'ArrowDown',
                    'y.high'  : meta+'ArrowUp'}

        item = self.addGlobalMap('config.plot')
        item.tools              .default  ='xpan,box_zoom,reset,save'
        item.boundary.overshoot .default  =.001
        item.keypress.reset     .default  ='Shift- '
        item.keypress.pan       .defaults = _gesture('Alt-')
        item.keypress.zoom      .defaults = _gesture('Shift-')

        self.addGlobalMap('project', message = '')
        self.addGlobalMap('project.plot')

    def access(self, key: Optional[str] = None) -> GlobalsAccess:
        "returns a GlobalsAccess to a given map"
        return GlobalsAccess(self, key)

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
                    overwrite = True):
        """
        Writes up the user preferences.

        If *overwrite* is *False*, the preferences are first read from file, then
        written again. Notwithstanding version patches, this is a no-change operation.
        """
        self.__model.writeconfig(configpath, anastore, patchname, index, overwrite)

    def readconfig(self, configpath, patchname = 'config'):
        "Sets-up the user preferences"
        cnf = self.__model.readconfig(configpath, anastore, patchname)
        if cnf is None or len(cnf) == 0:
            return

        with Action(self):
            for root, values in cnf.items():
                self.__maps[root].update(values)

    def __undos__(self):
        "yields all undoable user actions"
        def _onglobals(items):
            name = items.name
            if name == 'project':
                items.pop("track", None)
                items.pop("task",  None)
            elif name.startswith('project.plot.'):
                items.pop('x', None)
                items.pop('y', None)

            vals = {i: j.old for i, j in items}
            return lambda: self.updateGlobal(name, **vals)

        yield from ((key, _onglobals) for key in self.__maps)
