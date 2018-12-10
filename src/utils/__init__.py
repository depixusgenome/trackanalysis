#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"utils"
from copy           import deepcopy
from typing         import TypeVar, Tuple, cast
from dataclasses    import dataclass, field

import numpy as np

from .inspection    import (signature, ismethod, isfunction,
                            getmembers, isgeneratorfunction, getlocals)

from .attrdefaults  import (toenum, changefields, kwargsdefaults, setdefault,
                            initdefaults, update, updatecopy, updatedeepcopy,
                            NoArgs, DefaultValue)

from .decoration    import fromstream, escapenans, StreamUnion, cachedio, CachedIO
from .array         import (EventsArray, asdataarrays, asobjarray, asview,
                            EVENTS_DTYPE, EVENTS_TYPE)

Ints    = cast(Tuple[type], (np.int32, np.int64, int, np.int16, bool, np.bool_))
Floats  = cast(Tuple[type], (np.float32, np.float64, float))
Numbers = cast(Tuple[type], Ints + Floats)

def isint(val) -> bool:
    "return whether is an int"
    return isinstance(val, Ints)

def isfloat(val) -> bool:
    "return whether is an float"
    return isinstance(val, Floats)
def isnumber(val) -> bool:
    "return whether is an float"
    return isinstance(val, Numbers)

Type   = TypeVar("Type")
def dflt(default: Type, **kwa) -> Type:
    "return a field with default factory"
    return field(default_factory= lambda: deepcopy(default), **kwa)
