#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=arguments-differ
"Loading and save tracks"
import sys
from   pathlib                   import Path
from   typing                    import Optional, Union, Any, Dict, cast

import taskstore
from   taskmodel.__scripting__.track import LocalTasks
from   ..trackio                 import Handler, TrackIO
from   ..trackio                 import PATHTYPES, PATHTYPE, instrumentinfo
from   .track                    import Track

class ScriptAnaIO(TrackIO):
    "checks and opens taskstore paths"
    EXT = '.ana'
    @classmethod
    def check(cls, path:PATHTYPES, **_) -> Optional[PATHTYPES]:
        "checks the existence of a path"
        return cls.checkpath(path, cls.EXT)

    @staticmethod
    def __open(path):
        mdl = taskstore.load(str(path))['tasks'][0]
        cnf = mdl[0].config()
        rep = lambda x: x
        if sys.platform == 'linux':
            data = next((i for i in ('/media/biology/data', '/media/data')
                         if Path(i).exists()), None)
            if data is not None:
                rep = lambda x: Path(str(x)
                                     .replace("\\", "/")
                                     .replace('//samba.picoseq.org/shared/data',
                                              cast(str, data)))
        cnf['path']  = tuple(rep(i) for i in cnf['path'])
        return mdl, cnf

    @classmethod
    def instrumentinfo(cls, path: str) -> Dict[str, Any]:
        "return the instrument type"
        return instrumentinfo(cls.__open(str(path))[1]['path'][0])

    @classmethod
    def open(cls, path:PATHTYPE, **_) -> Dict[Union[str, int], Any]:
        "opens a track file"
        mdl, cnf = cls.__open(path)
        cnf      = Handler.todict(Track(**cnf))

        cnf['tasks'] = LocalTasks()
        cnf['tasks'].load(mdl[1:])
        return cnf

__all__: list = []
