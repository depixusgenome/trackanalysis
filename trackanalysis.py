#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Set this in your PYTHONPATH in order to start scripting easily"
import sys
from   pathlib   import Path

for path in (Path.home(), Path.home()/'work', Path('./build').resolve()):
    cur = path/'trackanalysis'/'build'
    if cur.exists() and str(cur) not in sys.path:
        sys.path.append(str(cur))
        break

# pylint: disable=wildcard-import,unused-wildcard-import,wrong-import-position
from  scripting import *
