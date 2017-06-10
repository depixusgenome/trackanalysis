#!/usr/bin/env python3
# encoding: utf-8
"wscript cut into pieces"
from pathlib import Path
try:
    from wafbuilder import _utils, default as _default
except ImportError as exc:
    raise ImportError("Don't forget to clone wafbuilder!!") from exc
_default('python', 'coffee')

_utils.INCORRECT.append(str(Path(__file__).parent))
_utils.ROOT      = str(Path(__file__).parent.parent)

# pylint: disable=wildcard-import,wrong-import-position
from ._requirements import *
from .              import base
from ._conda        import *
from ._tests        import *
from ._utils        import *
from .bokehcompiler import *
