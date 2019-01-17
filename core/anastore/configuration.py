#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Storing global properties"
from typing          import Callable, Optional
from utils.logconfig import getLogger
import anastore
LOGS = getLogger(__name__)

def writeconfig(maps, # pylint: disable=too-many-arguments
                configpath: Callable,
                patchname    = 'config',
                index        = 0,
                indent       = 4,
                ensure_ascii = False,
                sort_keys    = True,
                **kwa):
    "Writes up the user preferences."
    path = configpath(anastore.version(patchname))
    path.parent.mkdir(parents = True, exist_ok = True)
    path.touch(exist_ok = True)

    itr = ((i, j.maps[index] if hasattr(j, 'maps') else j) for i, j in maps.items())
    tmp = {i: j for i, j in itr if len(j)}

    anastore.dump(tmp, path,
                  patch        = patchname,
                  indent       = indent,
                  ensure_ascii = ensure_ascii,
                  sort_keys    = sort_keys,
                  **kwa)

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
