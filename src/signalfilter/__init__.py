#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Signal Analysis: filters, stats and interval detection"
from ._base             import (mediandeviation, nanmediandeviation,
                                nanhfsigma, hfsigma, PrecisionAlg, CppPrecisionAlg,
                                PRECISION)
from ._core.stats       import (nancount, # pylint: disable=no-name-in-module,import-error
                                nanthreshold)
from .noisereduction    import (RollingFilter, NonLinearFilter,
                                ForwardBackwardFilter, Filter)

rawprecision = PrecisionAlg.rawprecision # pylint: disable=invalid-name

__all__ = ['RollingFilter', 'NonLinearFilter', 'ForwardBackwardFilter',
           'hfsigma', 'nanhfsigma', 'rawprecision', 'mediandeviation',
           'nanmediandeviation']
