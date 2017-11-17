#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Storing global properties"
from typing          import Dict, Callable, Optional

from utils.logconfig import getLogger
from ._child         import GlobalsChild, delete
from ._access        import SingleMapAccess
LOGS    = getLogger(__name__)

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
    def __init__(self, **_):
        self.__maps: Dict[str, GlobalsChild] = dict()

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

        if protocol is dict:
            return (maps        if configpath is None else
                    {i: j for i, j in maps.items() if configpath(i)})

        path = configpath(protocol.version(patchname))
        path.parent.mkdir(parents = True, exist_ok = True)
        path.touch(exist_ok = True)

        protocol.dump(maps, path, patch = patchname, **kwa)

    def readconfig(self, configpath, protocol, patchname = 'config') -> Optional[dict]:
        "Sets-up the user preferences"
        if protocol is dict:
            cnf = configpath
        else:
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
