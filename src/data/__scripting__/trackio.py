#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=arguments-differ
"Loading and save tracks"
import sys
from   pathlib                   import Path
from   typing                    import Optional, Union, Any, Dict

import anastore
from   model.__scripting__.track import LocalTasks
from   ..trackio                 import Handler, _TrackIO # pylint: disable=protected-access
from   ..trackio                 import PATHTYPES, PATHTYPE
from   .track                    import Track

class ScriptAnaIO(_TrackIO):
    "checks and opens anastore paths"
    EXT = '.ana'
    @classmethod
    def check(cls, path:PATHTYPES, **_) -> Optional[PATHTYPES]:
        "checks the existence of a path"
        return cls.checkpath(path, cls.EXT)

    @staticmethod
    def open(path:PATHTYPE, **_) -> Dict[Union[str, int], Any]:
        "opens a track file"
        mdl = anastore.load(str(path))['tasks'][0]
        cnf = mdl[0].config()
        rep = lambda x: x
        if sys.platform == 'linux':
            data = next((i for i in ('/media/biology/data', '/media/data')
                         if Path(i).exists()), None)
            if data is not None:
                rep = lambda x: Path(str(x)
                                     .replace("\\", "/")
                                     .replace('//samba.picoseq.org/shared/data', data))
        cnf['path']  = tuple(rep(i) for i in cnf['path'])
        cnf          = Handler.todict(Track(**cnf))

        cnf['tasks'] = LocalTasks()
        cnf['tasks'].load(mdl[1:])
        return cnf

__all__: list = []
