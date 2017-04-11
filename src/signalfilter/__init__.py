#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Signal Analysis: filters, stats and interval detection"
from ._base             import nanhfsigma, hfsigma, PrecisionAlg
from ._core             import samples # pylint: disable=no-name-in-module,import-error
from .noisereduction    import (RollingFilter, NonLinearFilter,
                                ForwardBackwardFilter, Filter)

rawprecision = PrecisionAlg.rawprecision
