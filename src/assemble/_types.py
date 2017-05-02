#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from typing import NewType
import scipy.stats

SciDist = NewType("SciDist",scipy.stats._distn_infrastructure.rv_frozen) # pylint: disable=protected-access
