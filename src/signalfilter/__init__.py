#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Signal Analysis: filters, stats and interval detection"
# pylint: disable=no-name-in-module,import-error
from ._core         import (ForwardBackwardFilter,
                            NonLinearFilter)
from ._core.stats   import hfsigma
