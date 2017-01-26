#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Signal Analysis: filters, stats and interval detection"
# pylint: disable=no-name-in-module,import-error
import numpy as np
from ._core         import (ForwardBackwardFilter, NonLinearFilter, samples)
from ._core.stats   import hfsigma

def nanhfsigma(arr):
    u"hfsigma which takes care of nans"
    return hfsigma(arr[~np.isnan(arr)])
