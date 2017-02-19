#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Signal Analysis: filters, stats and interval detection"
# pylint: disable=no-name-in-module,import-error
from ._base             import nanhfsigma, PrecisionAlg
from ._core             import samples
from .noisereduction    import (RollingFilter, NonLinearFilter,
                                ForwardBackwardFilter, Filter)
