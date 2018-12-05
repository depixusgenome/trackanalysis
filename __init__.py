#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"utils"
from copy           import deepcopy
from typing         import TypeVar
from dataclasses    import dataclass, field
from .inspection    import (signature, ismethod, isfunction,
                            getmembers, isgeneratorfunction, getlocals)

from .attrdefaults  import (toenum, changefields, kwargsdefaults, setdefault,
                            initdefaults, update, updatecopy, updatedeepcopy,
                            NoArgs, DefaultValue)

from .decoration    import fromstream, escapenans, StreamUnion, cachedio, CachedIO
from .array         import (EventsArray, asdataarrays, asobjarray, asview,
                            EVENTS_DTYPE, EVENTS_TYPE)

Type = TypeVar("Type")
def dflt(default: Type, **kwa) -> Type:
    "return a field with default factory"
    return field(default_factory= lambda: deepcopy(default), **kwa)
