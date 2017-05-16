#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"utils"
from .inspection    import (signature, ismethod, isfunction,
                            getmembers, isgeneratorfunction, getlocals)

from .attrdefaults  import (toenum, changefields, kwargsdefaults, setdefault,
                            initdefaults, update, updatecopy, updatedeepcopy,
                            NoArgs)

from .decoration    import fromstream, escapenans, StreamUnion, cachedio, CachedIO
from .array         import asdataarrays, asobjarray, EVENTS_DTYPE, EVENTS_TYPE
