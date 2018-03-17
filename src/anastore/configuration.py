#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Storing global properties"
from typing          import Callable, Optional
from utils.logconfig import getLogger
import anastore
LOGS = getLogger(__name__)

def writeconfig(maps,
                configpath: Callable,
                patchname = 'config',
                index     = 0,
                **kwa):
    "Writes up the user preferences."
    if maps is None:
        maps = readconfig(configpath, patchname)
    else:
        maps = {i: j.maps[index] if hasattr(j, 'maps') else j
                for i, j in maps.items()}
        maps = {i: j for i, j in maps.items() if len(j)}

    path = configpath(anastore.version(patchname))
    path.parent.mkdir(parents = True, exist_ok = True)
    path.touch(exist_ok = True)
    anastore.dump(maps, path, patch = patchname, **kwa)

def readconfig(configpath, patchname = 'config', maps = None) -> Optional[dict]:
    "Sets-up the user preferences"
    cnf   = None
    first = True
    for version in anastore.iterversions(patchname):
        path = configpath(version)
        if not path.exists():
            continue
        try:
            cnf = anastore.load(path, patch = patchname)
        except Exception as exc: # pylint: disable=broad-except
            LOGS.warning("Failed loading %s", path, exc_info = exc)
            first = False
            continue
        (LOGS.debug if first else LOGS.info)("Loaded %s", path)
        break

    if cnf is None or maps is None:
        return cnf

    for root in frozenset(cnf) - frozenset(maps):
        cnf.pop(root)

    for root, values in tuple(cnf.items()):
        for key in frozenset(values) - frozenset(maps[root]):
            values.pop(key)
        if len(values) == 0:
            cnf.pop(root)
    return cnf
